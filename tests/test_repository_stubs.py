"""RFC-0020: el stub de Python debe exponer los RPCs y mensajes de repositorio
(el stub de Go vive en higpertext-server-profile; ambos se regeneran juntos)."""

from higpertext_mcp.gen.profile.v1 import profile_pb2, profile_pb2_grpc

REPOSITORY_RPCS = (
    "ResolveRepository",
    "ListRepositories",
    "GetRepositoryConfig",
    "SetRepositoryConfig",
    "PlanRepositoryMigration",
)


def test_project_service_stub_exposes_repository_rpcs():
    class Channel:
        def unary_unary(self, *args, **kwargs):
            return lambda *a, **k: None

    stub = profile_pb2_grpc.ProjectServiceStub(Channel())
    for rpc in REPOSITORY_RPCS:
        assert hasattr(stub, rpc), f"falta {rpc} en ProjectServiceStub"
    # Los RPCs existentes siguen ahí: el cambio es aditivo.
    for rpc in ("ResolveProject", "ListProjects", "AddProjectPath", "RemoveProjectPath", "RenameProject", "DeleteProject"):
        assert hasattr(stub, rpc)


def test_repository_messages_round_trip():
    request = profile_pb2.ResolveRepositoryRequest(path="/repos/a", remote="git@github.com:org/a.git", host_id="host-a")
    assert profile_pb2.ResolveRepositoryRequest.FromString(request.SerializeToString()) == request

    config = profile_pb2.RepositoryConfig(repository_id="r1", profile="devsecops", overrides={"assistant": "claude"})
    again = profile_pb2.RepositoryConfig.FromString(config.SerializeToString())
    assert again.profile == "devsecops" and dict(again.overrides) == {"assistant": "claude"}

    plan = profile_pb2.PlanRepositoryMigrationResponse(
        items=[profile_pb2.RepositoryMigrationItem(project_id="p", path="/x", action="create_local")],
        to_create=1,
    )
    assert plan.items[0].action == "create_local" and plan.to_create == 1
