from higpertext_mcp import schema


def test_build_input_schema_marks_required_params():
    parameters = [
        {"name": "pattern", "required": True, "description": "patrón"},
        {"name": "path", "required": False, "default": ".", "description": "ruta"},
    ]
    result = schema._build_input_schema(parameters)
    assert result["required"] == ["pattern"]
    assert result["properties"]["path"]["default"] == "."
    assert result["properties"]["pattern"]["type"] == "string"


def test_build_input_schema_no_required_omits_key():
    parameters = [{"name": "flag", "required": False}]
    result = schema._build_input_schema(parameters)
    assert "required" not in result


def test_build_input_schema_infers_boolean_type():
    parameters = [{"name": "regex", "required": False, "default": "false"}]
    result = schema._build_input_schema(parameters)
    assert result["properties"]["regex"]["type"] == "boolean"
    assert result["properties"]["regex"]["default"] == "false"


def test_build_input_schema_infers_integer_type():
    parameters = [{"name": "max_results", "required": False, "default": "100"}]
    result = schema._build_input_schema(parameters)
    assert result["properties"]["max_results"]["type"] == "integer"


def test_build_input_schema_no_default_stays_string():
    parameters = [{"name": "pattern", "required": True, "description": "patrón"}]
    result = schema._build_input_schema(parameters)
    assert result["properties"]["pattern"]["type"] == "string"


def test_build_description_includes_contract_rules():
    definition = {
        "description": "Busca patrones.",
        "contract": {"rules": ["Debe indicar coincidencias.", "Debe respetar límites."]},
    }
    result = schema._build_description(definition)
    assert "Busca patrones." in result
    assert "Debe indicar coincidencias." in result
    assert "Debe respetar límites." in result


def test_build_description_without_contract():
    definition = {"description": "Solo descripción."}
    result = schema._build_description(definition)
    assert result == "Solo descripción."


def test_load_tool_spec_unknown_capability_returns_none():
    assert schema.load_tool_spec("common.no-existe-esto") is None


def test_load_tool_spec_real_grep_search():
    """Requiere higpertext-cli instalado editable — valida contra el JSON real."""
    spec = schema.load_tool_spec("common.grep-search")
    assert spec is not None
    assert spec.capability_id == "common.grep-search"
    assert "pattern" in spec.input_schema["properties"]
    assert "path" in spec.input_schema["properties"]
