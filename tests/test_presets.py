from taskflow.presets import delete_filter_preset, get_filter_presets, save_filter_preset


def test_save_and_retrieve_preset(admin):
    success, message = save_filter_preset(admin["id"], "My Preset", {"mine_only": True})
    assert success, message
    presets = get_filter_presets(admin["id"])
    assert presets == [{"name": "My Preset", "payload": {"mine_only": True}}]


def test_saving_same_name_overwrites(admin):
    save_filter_preset(admin["id"], "P", {"a": 1})
    save_filter_preset(admin["id"], "P", {"a": 2})
    presets = get_filter_presets(admin["id"])
    assert len(presets) == 1
    assert presets[0]["payload"] == {"a": 2}


def test_presets_are_scoped_per_user(admin, member):
    save_filter_preset(admin["id"], "Admin Preset", {})
    save_filter_preset(member["id"], "Member Preset", {})
    assert [p["name"] for p in get_filter_presets(admin["id"])] == ["Admin Preset"]
    assert [p["name"] for p in get_filter_presets(member["id"])] == ["Member Preset"]


def test_delete_preset(admin):
    save_filter_preset(admin["id"], "Temp", {})
    success, message = delete_filter_preset(admin["id"], "Temp")
    assert success, message
    assert get_filter_presets(admin["id"]) == []


def test_delete_missing_preset_reports_failure(admin):
    success, message = delete_filter_preset(admin["id"], "Nope")
    assert not success


def test_empty_preset_name_rejected(admin):
    success, message = save_filter_preset(admin["id"], "   ", {})
    assert not success
