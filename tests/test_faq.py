"""FAQ entries are moderator-authored and start as a 'draft' - only visible
in /admin/faq, never on the public /faq page until explicitly published
(schema.sql's faq_entries, admin/faq.py, public.py's faq())."""
from conftest import seed_user


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def _add_entry(db, question, answer, status="draft", sort_order=0):
    db.execute(
        "INSERT INTO faq_entries (question, answer, status, sort_order) VALUES (?, ?, ?, ?)",
        (question, answer, status, sort_order),
    )
    db.commit()
    return db.execute("SELECT id FROM faq_entries WHERE question = ?", (question,)).fetchone()["id"]


def test_public_faq_shows_only_published_entries(client, db):
    _add_entry(db, "Published question", "Published answer", status="published", sort_order=0)
    _add_entry(db, "Draft question", "Draft answer", status="draft", sort_order=1)

    body = client.get("/faq").get_data(as_text=True)
    assert "Published question" in body
    assert "Draft question" not in body


def test_public_faq_respects_sort_order(client, db):
    _add_entry(db, "Second", "b", status="published", sort_order=1)
    _add_entry(db, "First", "a", status="published", sort_order=0)

    body = client.get("/faq").get_data(as_text=True)
    assert body.index("First") < body.index("Second")


def test_admin_faq_list_requires_login(client):
    resp = client.get("/admin/faq")
    assert resp.status_code == 302


def test_admin_faq_list_shows_drafts_too(client, db):
    admin_id = seed_user(db)
    _add_entry(db, "Draft question", "Draft answer", status="draft")

    login_as(client, admin_id)
    body = client.get("/admin/faq").get_data(as_text=True)
    assert "Draft question" in body


def test_new_entry_starts_as_draft(client, db):
    admin_id = seed_user(db)
    login_as(client, admin_id)

    resp = client.post(
        "/admin/faq/new",
        data={"question": "How do I join?", "answer": "Contact your local society."},
        follow_redirects=False,
    )
    assert resp.status_code == 302

    row = db.execute("SELECT * FROM faq_entries WHERE question = ?", ("How do I join?",)).fetchone()
    assert row["status"] == "draft"
    assert not any("How do I join?" in b for b in [client.get("/faq").get_data(as_text=True)])


def test_publish_makes_it_visible_publicly(client, db):
    admin_id = seed_user(db)
    entry_id = _add_entry(db, "What is AIMS?", "A national body for amateur musical societies.")
    login_as(client, admin_id)

    client.post(f"/admin/faq/{entry_id}/publish", follow_redirects=False)

    row = db.execute("SELECT status FROM faq_entries WHERE id = ?", (entry_id,)).fetchone()
    assert row["status"] == "published"
    assert "What is AIMS?" in client.get("/faq").get_data(as_text=True)


def test_unpublish_hides_it_again(client, db):
    admin_id = seed_user(db)
    entry_id = _add_entry(db, "Question", "Answer", status="published")
    login_as(client, admin_id)

    client.post(f"/admin/faq/{entry_id}/unpublish", follow_redirects=False)

    row = db.execute("SELECT status FROM faq_entries WHERE id = ?", (entry_id,)).fetchone()
    assert row["status"] == "draft"
    assert "Question" not in client.get("/faq").get_data(as_text=True)


def test_edit_updates_question_and_answer(client, db):
    admin_id = seed_user(db)
    entry_id = _add_entry(db, "Old question", "Old answer")
    login_as(client, admin_id)

    client.post(
        f"/admin/faq/{entry_id}/edit",
        data={"question": "New question", "answer": "New answer"},
        follow_redirects=False,
    )

    row = db.execute("SELECT * FROM faq_entries WHERE id = ?", (entry_id,)).fetchone()
    assert row["question"] == "New question"
    assert row["answer"] == "New answer"


def test_delete_removes_the_entry(client, db):
    admin_id = seed_user(db)
    entry_id = _add_entry(db, "Question", "Answer")
    login_as(client, admin_id)

    client.post(f"/admin/faq/{entry_id}/delete", follow_redirects=False)

    assert db.execute("SELECT 1 FROM faq_entries WHERE id = ?", (entry_id,)).fetchone() is None


def test_move_swaps_sort_order_with_neighbour(client, db):
    admin_id = seed_user(db)
    first_id = _add_entry(db, "First", "a", sort_order=0)
    second_id = _add_entry(db, "Second", "b", sort_order=1)
    login_as(client, admin_id)

    client.post(f"/admin/faq/{second_id}/move", data={"direction": "up"}, follow_redirects=False)

    first = db.execute("SELECT sort_order FROM faq_entries WHERE id = ?", (first_id,)).fetchone()
    second = db.execute("SELECT sort_order FROM faq_entries WHERE id = ?", (second_id,)).fetchone()
    assert second["sort_order"] < first["sort_order"]


def test_move_up_at_the_top_is_a_no_op(client, db):
    admin_id = seed_user(db)
    entry_id = _add_entry(db, "Only one", "a", sort_order=0)
    login_as(client, admin_id)

    resp = client.post(f"/admin/faq/{entry_id}/move", data={"direction": "up"}, follow_redirects=False)
    assert resp.status_code == 302

    row = db.execute("SELECT sort_order FROM faq_entries WHERE id = ?", (entry_id,)).fetchone()
    assert row["sort_order"] == 0
