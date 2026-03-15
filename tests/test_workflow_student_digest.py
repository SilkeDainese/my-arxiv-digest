from pathlib import Path

import yaml


WORKFLOW_PATH = (
    Path(__file__).resolve().parents[1] / ".github" / "workflows" / "student-digest.yml"
)


def _load_workflow():
    return yaml.safe_load(WORKFLOW_PATH.read_text())


def _step_by_name(workflow, name):
    steps = workflow["jobs"]["send-student-digests"]["steps"]
    return next(step for step in steps if step["name"] == name)


def _workflow_on_block(workflow):
    return workflow.get("on") or workflow.get(True)


def test_student_workflow_has_preview_dispatch_inputs():
    workflow = _load_workflow()
    inputs = _workflow_on_block(workflow)["workflow_dispatch"]["inputs"]

    assert inputs["preview"]["type"] == "boolean"
    assert inputs["recipient"]["type"] == "string"
    assert inputs["limit"]["type"] == "string"


def test_student_workflow_passes_preview_and_registry_env():
    workflow = _load_workflow()
    run_step = _step_by_name(workflow, "Send AU student digests")

    assert run_step["env"]["STUDENT_ADMIN_TOKEN"] == "${{ secrets.STUDENT_ADMIN_TOKEN }}"
    assert run_step["env"]["WORKFLOW_DISPATCH_PREVIEW"] == "${{ inputs.preview }}"
    assert run_step["env"]["WORKFLOW_DISPATCH_RECIPIENT"] == "${{ inputs.recipient }}"
    assert run_step["env"]["WORKFLOW_DISPATCH_LIMIT"] == "${{ inputs.limit }}"

    script = run_step["run"]
    assert "--preview --preview-dir student_previews" in script
    assert '--recipient "$WORKFLOW_DISPATCH_RECIPIENT"' in script
    assert '--limit "$WORKFLOW_DISPATCH_LIMIT"' in script


def test_student_workflow_uploads_preview_artifact():
    workflow = _load_workflow()
    upload_step = _step_by_name(workflow, "Upload preview artifact")

    assert "workflow_dispatch" in upload_step["if"]
    assert "inputs.preview" in upload_step["if"]
    assert upload_step["uses"].startswith("actions/upload-artifact@")
