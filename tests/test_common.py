from trustpack.common import GENESIS, TEMPLATE_LABEL, HashChain, canonical, sha256_hex


def test_canonical_is_key_order_independent():
    assert canonical({"b": 1, "a": 2}) == canonical({"a": 2, "b": 1}) == '{"a":2,"b":1}'


def test_sha256_known_vector():
    assert sha256_hex("abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_sha256_bytes_and_str_agree():
    assert sha256_hex(b"x") == sha256_hex("x")


def test_empty_chain_head_is_genesis():
    assert HashChain().head == GENESIS


def test_chain_links_prev_hash():
    c = HashChain()
    a = c.append({"n": 1})
    b = c.append({"n": 2})
    assert b["prev"] == a["hash"] and a["prev"] == GENESIS
    assert HashChain.verify(c.entries) is None


def test_chain_detects_edit():
    c = HashChain()
    for i in range(4):
        c.append({"n": i})
    c.entries[2]["body"]["n"] = 99
    assert HashChain.verify(c.entries) == 2


def test_chain_detects_removal_and_reorder():
    c = HashChain()
    for i in range(4):
        c.append({"n": i})
    assert HashChain.verify(c.entries[:1] + c.entries[2:]) == 1
    assert HashChain.verify([c.entries[1], c.entries[0]]) == 0


def test_template_label_wording():
    assert TEMPLATE_LABEL == "Template, not certified"
