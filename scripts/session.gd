extends RefCounted
## Pure training rules. Times are seconds on the audio timeline.
## This foundation deliberately accepts simulated input only.

enum State { READY, PLAYING, PAUSED, STAMP, RESULTS }
const PERFECT_WINDOW := 0.085
const HIT_WINDOW := 0.18
const DURATION := 36.0
const ACTIONS := ["left_jab", "right_jab", "left_hook", "right_hook"]

var duration := DURATION
var chart_id := "demo-120-v1"
var song_id := "demo"
var state := State.READY
var chart: Array[Dictionary] = []
var cursor := 0
var clock := 0.0
var score := 0
var combo := 0
var best_combo := 0
var hits := 0
var misses := 0
var attempts := 0
var feedback := "READY"

func start(arrangement: Dictionary = {}) -> void:
	chart.clear()
	duration = float(arrangement.get("duration", DURATION))
	chart_id = str(arrangement.get("id", "demo-120-v1"))
	song_id = str(arrangement.get("song_id", "demo"))
	# Fixed 120 BPM teaching pattern, with a four-second lead-in.
	var pattern := [0, 1, 0, 1, 2, 1, 0, 3]
	if arrangement.is_empty():
		for i in range(32):
			chart.append({"time": 4.0 + i, "action": ACTIONS[pattern[i % pattern.size()]]})
	else:
		for note in arrangement.notes:
			chart.append(note.duplicate())
	cursor = 0
	clock = 0.0
	score = 0
	combo = 0
	best_combo = 0
	hits = 0
	misses = 0
	attempts = 0
	feedback = "GET READY"
	state = State.PLAYING

func advance(time: float) -> void:
	if state != State.PLAYING:
		return
	clock = maxf(clock, time)
	while cursor < chart.size() and clock - float(chart[cursor].time) > HIT_WINDOW:
		misses += 1
		combo = 0
		feedback = "MISS"
		cursor += 1
	if clock >= duration:
		state = State.STAMP
		feedback = "ONE LAST PUNCH"

func punch(action: String, time: float) -> String:
	if state != State.PLAYING or action not in ACTIONS:
		return "IGNORED"
	advance(time)
	if state != State.PLAYING:
		return "IGNORED"
	attempts += 1
	if cursor >= chart.size():
		return "EMPTY"
	var note := chart[cursor]
	var delta := absf(clock - float(note.time))
	if delta > HIT_WINDOW:
		feedback = "EARLY"
		combo = 0
		return feedback
	if action != note.action:
		# Consume an incorrect strike; spamming all buttons cannot rescue a combo.
		misses += 1
		combo = 0
		cursor += 1
		feedback = "WRONG MOVE"
		return feedback
	hits += 1
	combo += 1
	best_combo = maxi(best_combo, combo)
	feedback = "PERFECT" if delta <= PERFECT_WINDOW else "GOOD"
	score += 100 if feedback == "PERFECT" else 60
	cursor += 1
	return feedback

func toggle_pause() -> void:
	if state == State.PLAYING:
		state = State.PAUSED
	elif state == State.PAUSED:
		state = State.PLAYING

func stamp() -> bool:
	if state != State.STAMP:
		return false
	state = State.RESULTS
	return true

func result() -> Dictionary:
	return {"mode": "simulation", "chart_id": chart_id, "song_id": song_id, "score": score,
		"hits": hits, "misses": misses, "attempts": attempts, "best_combo": best_combo,
		"duration_seconds": duration, "completed_at": Time.get_datetime_string_from_system(true)}
