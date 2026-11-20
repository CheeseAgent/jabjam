extends RefCounted
## Never mixes development input with future verified exercise records.
const PATH := "user://simulation_history.json"

static func read_history(path: String = PATH) -> Array:
	if not FileAccess.file_exists(path):
		return []
	var json := JSON.new()
	if json.parse(FileAccess.get_file_as_string(path)) != OK:
		return []
	var parsed: Variant = json.data
	if parsed is not Array:
		return []
	return parsed.filter(func(entry: Variant) -> bool:
		return entry is Dictionary and entry.get("mode") == "simulation")

static func save_result(result: Dictionary, path: String = PATH) -> Error:
	if result.get("mode") != "simulation":
		return ERR_INVALID_DATA
	var history := read_history(path)
	history.append(result)
	if history.size() > 100:
		history = history.slice(history.size() - 100)
	var file := FileAccess.open(path + ".tmp", FileAccess.WRITE)
	if file == null:
		return FileAccess.get_open_error()
	file.store_string(JSON.stringify(history, "\t"))
	file.flush()
	var error := file.get_error()
	file.close()
	if error != OK:
		return error
	return DirAccess.rename_absolute(path + ".tmp", path)
