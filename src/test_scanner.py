from scanner import _is_candidate, _rank

assert _is_candidate("package.json", 500) is True
assert _is_candidate("src/main.js", 500) is True
assert _is_candidate("node_modules/foo/index.js", 500) is False
assert _is_candidate("assets/logo.png", 500) is False
assert _is_candidate("src/big.js", 999_999) is False
assert _is_candidate("README.md", 500) is False

assert _rank("package.json")[0] == 0
assert _rank("src/main.js")[0] == 1
assert _rank("src/utils.js")[0] == 2

print("ok")
