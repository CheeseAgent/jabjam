extends RefCounted
## All audio stays under user://songs; only this local library owns its copies.
const Generator = preload("res://scripts/chart_generator.gd")
const ROOT := "user://songs"
const MAX_BYTES := 64 * 1024 * 1024
const FORMATS := ["mp3", "wav", "ogg"]
var root_path: String

func _init(directory: String = ROOT) -> void:
	root_path = directory

static func read_json(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var json := JSON.new()
	if json.parse(FileAccess.get_file_as_string(path)) != OK or json.data is not Dictionary:
		return {}
	return json.data

static func write_json(path: String, value: Dictionary) -> Error:
	var file := FileAccess.open(path + ".tmp", FileAccess.WRITE)
	if file == null:
		return FileAccess.get_open_error()
	file.store_string(JSON.stringify(value))
	file.flush()
	var error := file.get_error()
	file.close()
	return DirAccess.rename_absolute(path + ".tmp", path) if error == OK else error

func songs() -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	if not DirAccess.dir_exists_absolute(root_path):
		return result
	for id in DirAccess.get_directories_at(root_path):
		if id.length() != 64 or not id.is_valid_hex_number():
			continue
		var song := read_json(root_path.path_join(id).path_join("song.json"))
		if song.get("id") == id and song.get("extension") in FORMATS and song.get("title") is String and song.get("duration") is float:
			if not is_finite(song.duration) or song.duration < 8 or song.duration > 600:
				continue
			if FileAccess.file_exists(audio_path(song)):
				result.append(song)
	result.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return a.title.naturalnocasecmp_to(b.title) < 0)
	return result

func audio_path(song: Dictionary) -> String:
	return root_path.path_join(song.id).path_join("audio." + str(song.extension))

func import_song(path: String, difficulty := "normal", bpm_override := 0.0,
		progress: Callable = Callable()) -> Dictionary:
	var extension := path.get_extension().to_lower()
	if extension not in FORMATS:
		return {"error": "Supported formats: MP3, WAV, Ogg Vorbis. FLAC is not supported yet."}
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		return {"error": "Cannot read this file. Check its location and permissions."}
	if file.get_length() < 16 or file.get_length() > MAX_BYTES:
		return {"error": "Choose an audio file smaller than 64 MiB."}
	var bytes := file.get_buffer(file.get_length())
	file.close()
	if progress.is_valid() and not progress.call(0.0):
		return {"error": "Cancelled."}
	var stream := decode(bytes, extension)
	if stream == null:
		return {"error": "Invalid or unsupported audio. Try exporting it as PCM WAV, MP3 or Vorbis."}
	var duration := stream.get_length()
	if not is_finite(duration) or duration < 8.0 or duration > 600.0:
		return {"error": "Choose a song between 8 seconds and 10 minutes."}
	var hashing := HashingContext.new()
	hashing.start(HashingContext.HASH_SHA256)
	hashing.update(bytes)
	var id := hashing.finish().hex_encode()
	var directory := root_path.path_join(id)
	var chart_id := (id + "|" + Generator.VERSION + "|" + difficulty + "|" + str(bpm_override)).sha256_text()
	var chart_path := directory.path_join(chart_id + ".json")
	var chart := read_json(chart_path)
	if not Generator.valid(chart, id, duration) or chart.get("id") != chart_id:
		var analysis := Generator.analyze(stream, progress)
		chart = Generator.generate(analysis, id, duration, difficulty, bpm_override)
		if chart.has("error"):
			return chart
		# Match first-use and reload precision exactly at the persistence boundary.
		var canonical := JSON.new()
		canonical.parse(JSON.stringify(chart))
		chart = canonical.data
	if progress.is_valid() and not progress.call(1.0):
		return {"error": "Cancelled."}
	if DirAccess.make_dir_recursive_absolute(directory) != OK:
		return {"error": "Cannot create the local song library."}
	var song := read_json(directory.path_join("song.json"))
	var title := path.get_file().get_basename()
	if song.get("title") is String:
		title = song.title
	song = {"id": id, "title": title, "extension": extension, "duration": duration, "chart_id": chart_id}
	var destination := audio_path(song)
	# Recopy only when necessary, and atomically replace after writing all bytes.
	if not FileAccess.file_exists(destination) or FileAccess.get_sha256(destination) != id:
		var output := FileAccess.open(destination + ".tmp", FileAccess.WRITE)
		if output == null:
			return {"error": "Cannot save the local audio copy."}
		output.store_buffer(bytes)
		output.flush()
		var error := output.get_error()
		output.close()
		if error != OK or DirAccess.rename_absolute(destination + ".tmp", destination) != OK:
			return {"error": "Saving the audio failed. Check free disk space."}
	if write_json(chart_path, chart) != OK or write_json(directory.path_join("song.json"), song) != OK:
		return {"error": "Cannot save the generated chart."}
	return {"song": song, "chart": chart, "stream": stream}

static func decode(bytes: PackedByteArray, extension: String) -> AudioStream:
	if bytes.size() < 16:
		return null
	var stream: AudioStream
	match extension:
		"wav":
			if bytes.slice(0, 4).get_string_from_ascii() != "RIFF" or bytes.slice(8, 12).get_string_from_ascii() != "WAVE":
				return null
			stream = AudioStreamWAV.load_from_buffer(bytes, {"force/max_rate": true, "force/max_rate_hz": 44100})
		"mp3":
			if bytes.slice(0, 3).get_string_from_ascii() != "ID3" and not (bytes[0] == 255 and bytes[1] & 224 == 224):
				return null
			stream = AudioStreamMP3.load_from_buffer(bytes)
		"ogg":
			if bytes.slice(0, 4).get_string_from_ascii() != "OggS":
				return null
			stream = AudioStreamOggVorbis.load_from_buffer(bytes)
	if stream is AudioStreamWAV:
		stream.loop_mode = AudioStreamWAV.LOOP_DISABLED
	elif stream is AudioStreamMP3 or stream is AudioStreamOggVorbis:
		stream.loop = false
	return stream
