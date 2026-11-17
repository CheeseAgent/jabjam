extends RefCounted
## Worker owns decoding and filesystem work; UI only polls under the mutex.
const Library = preload("res://scripts/song_library.gd")
var thread := Thread.new()
var mutex := Mutex.new()
var cancelled := false
var progress := 0.0

func start(path: String, difficulty: String, bpm: float, library_root := Library.ROOT) -> Error:
	return thread.start(func() -> Dictionary:
		return Library.new(library_root).import_song(path, difficulty, bpm, _report))

func _report(value: float) -> bool:
	mutex.lock()
	progress = value
	var keep_going := not cancelled
	mutex.unlock()
	return keep_going

func cancel() -> void:
	mutex.lock()
	cancelled = true
	mutex.unlock()

func fraction() -> float:
	mutex.lock()
	var value := progress
	mutex.unlock()
	return value

func finish() -> Dictionary:
	return thread.wait_to_finish()
