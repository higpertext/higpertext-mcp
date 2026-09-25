from higpertext_mcp import schema
from higpertext_mcp.gen.profile.v1 import profile_pb2


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
    assert result["properties"]["regex"]["default"] is False


def test_build_input_schema_exposes_enum_values():
    parameters = [{"name": "action", "type": "string", "enum_values": ["list", "remove"]}]
    result = schema._build_input_schema(parameters)
    assert result["properties"]["action"]["enum"] == ["list", "remove"]


def test_common_legacy_parameters_are_exposed_with_rich_types():
    cap = profile_pb2.Capability(
        id="common.grep-search",
        parameters=[
            profile_pb2.Parameter(name="include", default=""),
            profile_pb2.Parameter(name="regex", default="false"),
            profile_pb2.Parameter(name="max_results", default="100"),
            profile_pb2.Parameter(name="preset", default="all"),
        ],
    )
    result = schema.tool_spec_from_capability(cap).input_schema["properties"]
    assert result["include"]["type"] == "array"
    assert result["include"]["items"] == {"type": "string"}
    assert result["regex"]["type"] == "boolean"
    assert result["regex"]["default"] is False
    assert result["max_results"]["type"] == "integer"
    assert result["preset"]["enum"] == ["all", "code", "python", "web", "docs", "config"]


def test_build_input_schema_infers_integer_type():
    parameters = [{"name": "max_results", "required": False, "default": "100"}]
    result = schema._build_input_schema(parameters)
    assert result["properties"]["max_results"]["type"] == "integer"


def test_build_input_schema_no_default_stays_string():
    parameters = [{"name": "pattern", "required": True, "description": "patrón"}]
    result = schema._build_input_schema(parameters)
    assert result["properties"]["pattern"]["type"] == "string"


def test_build_description_omits_parameters_and_contract_rules():
    definition = {
        "description": "Busca patrones.",
        "parameters": [{"name": "pattern", "required": True, "description": "patrón"}],
        "contract": {"rules": ["Debe indicar coincidencias.", "Debe respetar límites."]},
    }
    result = schema._build_description(definition)
    assert result == "Busca patrones."


def test_build_description_without_contract():
    definition = {"description": "Solo descripción."}
    result = schema._build_description(definition)
    assert result == "Solo descripción."


def test_build_description_includes_on_empty():
    definition = {
        "description": "Busca patrones.",
        "contract": {"on_empty": "No encontrar nada es válido, no reintentes."},
    }
    result = schema._build_description(definition)
    assert "Si no hay resultados: No encontrar nada es válido, no reintentes." in result


def test_build_description_omits_on_empty_when_absent():
    definition = {
        "description": "Busca patrones.",
        "contract": {"rules": ["Debe indicar coincidencias."]},
    }
    result = schema._build_description(definition)
    assert "Si no hay resultados" not in result


def test_tool_spec_from_capability_builds_schema_and_description():
    cap = profile_pb2.Capability(
        id="common.grep-search",
        description="Busca patrones.",
        entrypoint="capabilities/common/scripts/core/search/grep_search.py",
        language="python",
        parameters=[
            profile_pb2.Parameter(name="pattern", required=True, description="patrón"),
            profile_pb2.Parameter(name="path", required=False, default=".", description="ruta"),
        ],
        contract=profile_pb2.Contract(
            rules=["Debe indicar coincidencias."], on_empty="No hay resultados."
        ),
    )
    spec = schema.tool_spec_from_capability(cap)

    assert spec.capability_id == "common.grep-search"
    assert "pattern" in spec.input_schema["properties"]
    assert spec.input_schema["properties"]["path"]["default"] == "."
    assert spec.input_schema["required"] == ["pattern"]
    assert "Busca patrones." in spec.description
    assert "Debe indicar coincidencias." not in spec.description
    assert "Si no hay resultados: No hay resultados." in spec.description
    assert spec.raw["entrypoint"] == "capabilities/common/scripts/core/search/grep_search.py"
    assert spec.raw["language"] == "python"


def test_tool_spec_from_capability_empty_default_is_omitted():
    cap = profile_pb2.Capability(
        id="common.x",
        parameters=[profile_pb2.Parameter(name="flag", required=False)],
    )
    spec = schema.tool_spec_from_capability(cap)
    assert "default" not in spec.input_schema["properties"]["flag"]
