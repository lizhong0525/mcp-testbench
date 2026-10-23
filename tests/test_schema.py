import unittest

from mcp_testbench.schema import validate_tools


def make_tool(name="echo", schema=None):
    if schema is None:
        schema = {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        }
    return {"name": name, "inputSchema": schema}


class ValidateToolsTest(unittest.TestCase):
    def test_valid_tools_have_no_issues(self):
        self.assertEqual(validate_tools([make_tool(), make_tool("add")]), [])

    def test_missing_name(self):
        issues = validate_tools([{"inputSchema": {"type": "object"}}])
        self.assertTrue(any("name" in i for i in issues))

    def test_duplicate_names(self):
        issues = validate_tools([make_tool("x"), make_tool("x")])
        self.assertTrue(any("duplicate" in i for i in issues))

    def test_missing_input_schema(self):
        tool = {"name": "echo"}
        issues = validate_tools([tool])
        self.assertTrue(any("inputSchema" in i for i in issues))

    def test_wrong_schema_type(self):
        issues = validate_tools([make_tool(schema={"type": "string"})])
        self.assertTrue(any("expected 'object'" in i for i in issues))

    def test_required_field_not_in_properties(self):
        schema = {"type": "object", "properties": {}, "required": ["text"]}
        issues = validate_tools([make_tool(schema=schema)])
        self.assertTrue(any("not declared" in i for i in issues))

    def test_property_without_type(self):
        schema = {"type": "object", "properties": {"text": {}}}
        issues = validate_tools([make_tool(schema=schema)])
        self.assertTrue(any("no type" in i for i in issues))

    def test_non_dict_tool(self):
        issues = validate_tools(["not-a-tool"])
        self.assertTrue(any("not an object" in i for i in issues))


if __name__ == "__main__":
    unittest.main()
