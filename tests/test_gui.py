from promptadour._gui import _get_tag_counts



def test_get_tag_counts():
    taglist = [
        ["foo"],
        ["foo", "bar"],
        ["foo"]
    ]
    counter = _get_tag_counts(taglist)
    assert len(counter) == 2
    assert counter["foo"] == 3
    assert counter["bar"] == 1