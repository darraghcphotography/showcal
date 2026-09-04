"""A 2026-09-04 site review found 4 of 15 sampled venue detail pages
overflowing sideways on a phone (3px-38px, e.g. National Opera House
Wexford, The Dean Crowe Theatre) - all with a long, unbroken value in
.detail-list (style.css), a 2-column grid keyed `max-content 1fr`.

A bare `1fr` grid track is actually `minmax(auto, 1fr)`, so unwrapped
content (a long venue website URL, in every failing case) forces the
track - and the page - wider than the viewport. pytest can't measure a
rendered layout, but it can assert the two rules that make the browser's
layout engine actually shrink the track: `minmax(0, 1fr)` on the column,
and `overflow-wrap: break-word` so a long word inside it can break."""


def _detail_list_rule():
    css = open("app/static/style.css", encoding="utf-8").read()
    start = css.index("\n.detail-list {") + 1
    end = css.index("\n", start)
    return css[start:end]


def test_detail_list_column_can_actually_shrink():
    rule = _detail_list_rule()
    assert "minmax(0, 1fr)" in rule, (
        "a bare 1fr track is minmax(auto, 1fr) - long unwrapped content "
        "(e.g. a venue's website URL) forces it wider than the page"
    )


def test_detail_list_values_can_wrap():
    css = open("app/static/style.css", encoding="utf-8").read()
    start = css.index("\n.detail-list dd {") + 1
    end = css.index("\n", start)
    rule = css[start:end]
    assert "overflow-wrap: break-word" in rule
