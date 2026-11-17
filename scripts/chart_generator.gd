extends RefCounted
## Deterministic local heuristic, not semantic mood or variable-tempo recognition.
const VERSION := "energy-grid-v1"
const STEP := 0.02
const SAMPLE_RATE := 8000.0
const ACTIONS := ["left_jab", "right_jab", "left_hook", "right_hook"]

static func analyze(stream: AudioStream, progress: Callable = Callable()) -> Dictionary:
	var duration := stream.get_length()
	var playback := stream.instantiate_playback()
	if playback == null:
		return {"error": "This audio could not be decoded."}
	playback.start()
	var energy := PackedFloat32Array()
	var frames := int(SAMPLE_RATE * STEP)
	var scale := float(AudioServer.get_mix_rate()) / SAMPLE_RATE
	var count := int(ceil(duration / STEP))
	for i in range(count):
		if i % 50 == 0 and progress.is_valid() and not progress.call(float(i) / count):
			playback.stop()
			return {"error": "Cancelled."}
		var samples := playback.mix_audio(scale, frames)
		var sum := 0.0
		for sample in samples:
			sum += (sample.x * sample.x + sample.y * sample.y) * 0.5
		energy.append(sqrt(sum / maxi(1, samples.size())))
	playback.stop()
	var peak := 0.0
	var novelty := PackedFloat32Array()
	for i in range(energy.size()):
		peak = maxf(peak, energy[i])
		novelty.append(maxf(0.0, energy[i] - energy[maxi(0, i - 1)]))
	if peak < 0.001:
		return {"error": "This file is silent or too quiet to arrange."}
	# Autocorrelation over up to two minutes. Prefer the shorter period on ties.
	var best_lag := 25
	var confidence := 0.0
	var limit := mini(novelty.size(), 6000)
	for lag in range(17, 51):
		var dot := 0.0
		var a := 0.0
		var b := 0.0
		for i in range(lag, limit):
			dot += novelty[i] * novelty[i - lag]
			a += novelty[i] * novelty[i]
			b += novelty[i - lag] * novelty[i - lag]
		var correlation := dot / maxf(0.00000001, sqrt(a * b))
		if correlation > confidence + 0.015:
			confidence = correlation
			best_lag = lag
	return {"energy": energy, "novelty": novelty, "peak": peak,
		"estimated_bpm": 60.0 / (best_lag * STEP), "confidence": confidence}

static func generate(analysis: Dictionary, song_id: String, duration: float,
		difficulty: String = "normal", bpm_override: float = 0.0) -> Dictionary:
	if analysis.has("error"):
		return analysis
	if difficulty not in ["easy", "normal"] or (bpm_override != 0.0 and (bpm_override < 60 or bpm_override > 180)):
		return {"error": "Choose Easy / Normal and a BPM between 60 and 180."}
	var bpm: float = bpm_override if bpm_override > 0 else analysis.estimated_bpm
	var period := 60.0 / bpm
	var energy: PackedFloat32Array = analysis.energy
	var novelty: PackedFloat32Array = analysis.novelty
	var bins := maxi(1, int(round(period / STEP)))
	var phase_scores := PackedFloat32Array()
	phase_scores.resize(bins)
	for i in range(novelty.size()):
		phase_scores[mini(bins - 1, int(fposmod(i * STEP, period) / period * bins))] += novelty[i]
	var phase_index := 0
	for i in range(bins):
		if phase_scores[i] > phase_scores[phase_index]:
			phase_index = i
	var phase := float(phase_index) / bins * period
	var minimum_gap := 1.1 if difficulty == "easy" else 0.7
	var stride := maxi(1, int(ceil(minimum_gap / period)))
	var notes: Array[Dictionary] = []
	var sections: Array[Dictionary] = []
	# Four-second energy regions produce rests and quieter/livelier phrases.
	for begin in range(0, energy.size(), 200):
		var total := 0.0
		for i in range(begin, mini(begin + 200, energy.size())):
			total += energy[i]
		sections.append({"time": begin * STEP, "energy": total / mini(200, energy.size() - begin)})
	var maximum_region := 0.0001
	for section in sections:
		maximum_region = maxf(maximum_region, section.energy)
	var beat := 0
	var phrase := song_id.substr(0, 8).hex_to_int() % 2
	while phase + beat * period < duration - 0.5:
		var time := phase + beat * period
		beat += 1
		if time < 3.0 or (beat - 1) % stride != 0:
			continue
		var region: Dictionary = sections[mini(int(time / 4.0), sections.size() - 1)]
		var level: float = region.energy / maximum_region
		if level < 0.08 or (level < 0.45 and (beat - 1) % (stride * 2) != 0):
			continue
		# Skip truly silent local windows, even inside an otherwise loud region.
		var local_peak := 0.0
		var frame := int(time / STEP)
		for i in range(maxi(0, frame - 8), mini(frame + 9, energy.size())):
			local_peak = maxf(local_peak, energy[i])
		if local_peak < maxf(0.001, float(analysis.peak) * 0.025):
			continue
		if not notes.is_empty():
			var previous: Dictionary = notes.back()
			var recovery := maxf(minimum_gap, 1.0) if str(previous.action).ends_with("hook") else minimum_gap
			# One extra recovery beat after each eight-note phrase.
			if notes.size() % 8 == 0:
				recovery = maxf(recovery, period * 2.0)
			if time - float(previous.time) < recovery - 0.001:
				continue
		var hand := notes.size() % 2
		var hook := difficulty == "normal" and level >= 0.45 and (notes.size() + phrase * 4) % 8 in [2, 5]
		var action: String = ACTIONS[hand + (2 if hook else 0)]
		notes.append({"time": snappedf(time, 0.001), "action": action})
	if notes.size() < 4:
		return {"error": "Not enough rhythmic audio. Try a longer or more percussive song."}
	var chart_id := (song_id + "|" + VERSION + "|" + difficulty + "|" + str(bpm_override)).sha256_text()
	return {"id": chart_id, "song_id": song_id, "version": VERSION, "difficulty": difficulty,
		"bpm_override": bpm_override, "bpm": snappedf(bpm, 0.1), "confidence": analysis.confidence,
		"duration": duration, "notes": notes, "sections": sections}

static func valid(chart: Dictionary, song_id: String, duration: float) -> bool:
	if chart.get("version") != VERSION or chart.get("song_id") != song_id:
		return false
	if chart.get("notes") is not Array or chart.notes.size() < 4 or chart.notes.size() > 1000:
		return false
	if typeof(chart.get("duration")) not in [TYPE_INT, TYPE_FLOAT] or typeof(chart.get("bpm")) not in [TYPE_INT, TYPE_FLOAT]:
		return false
	if not is_finite(float(chart.duration)) or absf(float(chart.duration) - duration) > 0.05:
		return false
	if not is_finite(float(chart.get("bpm", -1))) or float(chart.get("bpm", -1)) < 60 or float(chart.get("bpm", -1)) > 180:
		return false
	if chart.get("difficulty") not in ["easy", "normal"]:
		return false
	var previous := -10.0
	for note in chart.notes:
		if note is not Dictionary or note.get("action") not in ACTIONS:
			return false
		if typeof(note.get("time")) not in [TYPE_INT, TYPE_FLOAT]:
			return false
		var time := float(note.get("time", -1))
		if not is_finite(time) or time < 3.0 or time > duration - 0.4 or time - previous < 0.65:
			return false
		previous = time
	return true
