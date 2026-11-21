extends RefCounted
## Deterministic local heuristic, not semantic mood or variable-tempo recognition.
const VERSION := "onset-grid-v3"
const STEP := 0.01
const SECTION_FRAMES := 400  # Four seconds at the analysis hop.
const SAMPLE_RATE := 8000.0
const ACTIONS := ["left_jab", "right_jab", "left_hook", "right_hook"]

static func analyze(stream: AudioStream, progress: Callable = Callable()) -> Dictionary:
	var duration := stream.get_length()
	var playback := stream.instantiate_playback()
	if playback == null:
		return {"error": "This audio could not be decoded."}
	playback.start()
	var energy := PackedFloat32Array()
	var bass_energy := PackedFloat32Array()
	var lowpass := Vector2.ZERO
	var bass_alpha := 1.0 - exp(-TAU * 160.0 / SAMPLE_RATE)
	var frames := int(SAMPLE_RATE * STEP)
	var scale := float(AudioServer.get_mix_rate()) / SAMPLE_RATE
	var count := int(ceil(duration / STEP))
	energy.resize(count)
	bass_energy.resize(count)
	for i in range(count):
		if i % 50 == 0 and progress.is_valid() and not progress.call(float(i) / count):
			playback.stop()
			return {"error": "Cancelled."}
		var samples := playback.mix_audio(scale, frames)
		var sum := 0.0
		var bass_sum := 0.0
		for sample in samples:
			sum += sample.length_squared() * 0.5
			lowpass += (sample - lowpass) * bass_alpha
			bass_sum += lowpass.length_squared() * 0.5
		energy[i] = sqrt(sum / maxi(1, samples.size()))
		bass_energy[i] = sqrt(bass_sum / maxi(1, samples.size()))
	playback.stop()
	var peak := 0.0
	var novelty := PackedFloat32Array()
	novelty.resize(energy.size())
	for i in range(energy.size()):
		peak = maxf(peak, energy[i])
		var prev := maxi(0, i - 1)
		novelty[i] = maxf(0.0, energy[i] - energy[prev]) + maxf(0.0, bass_energy[i] - bass_energy[prev])
	if peak < 0.001:
		return {"error": "This file is silent or too quiet to arrange."}
	var analysis := _estimate_tempo(novelty)
	analysis.merge({"energy": energy, "novelty": novelty, "peak": peak})
	return analysis

static func _estimate_tempo(novelty: PackedFloat32Array) -> Dictionary:
	# A single quantized lag drifts across a song. Measure the same period across
	# progressively longer groups of beats, with sub-bin peak interpolation.
	var limit := mini(novelty.size(), int(120.0 / STEP))
	var shortest := floori(60.0 / (180.0 * STEP))
	var longest := ceili(60.0 / (60.0 * STEP))
	var lag := 0.5 / STEP
	var confidence := 0.0
	for candidate in range(shortest, longest + 1):
		var score := _correlation(novelty, candidate, limit)
		if score > confidence + 0.015:
			confidence = score
			lag = candidate
	var uncertainty := 1.25
	for span in [4, 8, 16, 32]:
		var center := roundi(lag * span)
		if center > limit / 3.0:
			break
		var radius := ceili(uncertainty * span)
		var best := center
		var peak_score := 0.0
		for candidate in range(center - radius, center + radius + 1):
			var score := _correlation(novelty, candidate, limit)
			if score > peak_score:
				peak_score = score
				best = candidate
		if peak_score < confidence * 0.4:
			continue
		var left := _correlation(novelty, best - 1, limit)
		var right := _correlation(novelty, best + 1, limit)
		var curvature := 2.0 * peak_score - left - right
		var fraction := clampf(0.5 * (right - left) / curvature, -0.5, 0.5) if curvature > 0.00001 else 0.0
		lag = (best + fraction) / float(span)
		uncertainty = 1.5 / float(span)
	return {"estimated_bpm": clampf(60.0 / (lag * STEP), 60.0, 180.0), "confidence": confidence}

static func _correlation(novelty: PackedFloat32Array, lag: int, limit: int) -> float:
	var dot := 0.0
	var a := 0.0
	var b := 0.0
	for i in range(lag, limit):
		var x := novelty[i]
		var y := novelty[i - lag]
		dot += x * y
		a += x * x
		b += y * y
	return dot / maxf(0.00000001, sqrt(a * b))

static func _beat_grid(novelty: PackedFloat32Array, period: float, duration: float) -> Array[float]:
	var bins := roundi(period / STEP)
	var histogram := PackedFloat32Array()
	histogram.resize(bins)
	for i in range(novelty.size()):
		var pos := fposmod(i * STEP, period) * bins / period
		var slot := floori(pos)
		var fraction := pos - slot
		histogram[slot % bins] += novelty[i] * (1.0 - fraction)
		histogram[(slot + 1) % bins] += novelty[i] * fraction
	var best_bin := 0
	var best_score := -1.0
	for i in range(bins):
		var score := 2.0 * histogram[i] + histogram[posmod(i-1, bins)] + histogram[(i+1) % bins]
		if score > best_score:
			best_score = score
			best_bin = i
	var phase := best_bin * period / bins
	var beats: Array[float] = []
	for n in range(ceili(duration / period) + 1):
		var center := phase + n * period
		var time := snappedf(maxf(0.0, center + _local_phase(center, period, novelty)), 0.001)
		if time >= duration:
			break
		beats.append(time)
	return beats

static func _local_phase(center: float, period: float, novelty: PackedFloat32Array) -> float:
	# Require evidence across surrounding beats before shifting the hit. A lone
	# syncopated syllable or hi-hat should not pull a combination off its pulse.
	var reach := roundi(minf(0.10, 0.20 * period) / STEP)
	var best := 0
	var high := 0.0
	var total := 0.0
	for offset in range(-reach, reach + 1):
		var score := 0.0
		for neighbor in range(-4, 5):
			var i := roundi((center + neighbor * period) / STEP) + offset
			if i >= 1 and i + 1 < novelty.size():
				score += (5 - absi(neighbor)) * (novelty[i-1] + 2.0 * novelty[i] + novelty[i+1])
		# Prefer the global phase on weak evidence or near-ties.
		score *= 1.0 - 0.20 * absf(float(offset) / reach)
		total += score
		if score > high:
			high = score
			best = offset
	if high <= 0.0001 or high < 1.35 * total / (2 * reach + 1):
		return 0.0
	return best * STEP


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
	var beats := _beat_grid(novelty, period, duration)
	var minimum_gap := 1.1 if difficulty == "easy" else 0.45
	var notes: Array[Dictionary] = []
	var sections: Array[Dictionary] = []
	# Describe the dynamic envelope: a four-second section is NOT a verse/chorus classifier.
	var maximum_region := 0.0001
	for begin in range(0, energy.size(), SECTION_FRAMES):
		var total := 0.0
		for i in range(begin, mini(begin + SECTION_FRAMES, energy.size())):
			total += energy[i]
		var average := total / mini(SECTION_FRAMES, energy.size() - begin)
		sections.append({"time": begin * STEP, "energy": average})
		maximum_region = maxf(maximum_region, average)
	# Avoid a hard four-second step at each boundary.
	for i in range(sections.size()):
		var before: float = sections[maxi(0, i - 1)].energy
		var current: float = sections[i].energy
		var after: float = sections[mini(sections.size() - 1, i + 1)].energy
		sections[i]["intensity"] = (before + current * 2.0 + after) / (4.0 * maximum_region)
	for beat in range(beats.size()):
		var time := beats[beat]
		var beat_in_phrase := beat % 8
		if time < 3.0 or time >= duration - 0.5:
			continue
		var region: Dictionary = sections[mini(int(time / 4.0), sections.size() - 1)]
		var level: float = region.intensity
		if level < 0.09:
			continue
		var active := false
		if difficulty == "easy":
			active = beat_in_phrase in [0, 4] if level < 0.65 else beat_in_phrase in [0, 2, 4, 6]
		elif level >= 0.68:
			# Two short three-punch runs per 8 beats, separated by deliberate rests.
			active = beat_in_phrase in [0, 1, 2, 4, 5, 6]
		elif level >= 0.35:
			active = beat_in_phrase in [0, 2, 4, 6]
		else:
			active = beat_in_phrase in [0, 4]
		if not active:
			continue
		# Avoid plotting a note over actual silence even inside a loud section.
		var local_peak := 0.0
		var frame := int(time / STEP)
		for i in range(maxi(0, frame - 16), mini(frame + 17, energy.size())):
			local_peak = maxf(local_peak, energy[i])
		if local_peak < maxf(0.001, float(analysis.peak) * 0.025):
			continue
		if not notes.is_empty():
			var previous: Dictionary = notes.back()
			var recovery := minimum_gap
			if str(previous.action).ends_with("hook"):
				recovery = maxf(recovery, 0.90)
			if time - float(previous.time) < recovery - 0.001:
				continue
		# Phrase-relative hooks rather than every N accepted notes. Hand alternation
		# is maintained across rests; an eight-beat burst has a natural reset.
		var hand := notes.size() % 2
		var hook := difficulty == "normal" and level >= 0.68 and beat_in_phrase in [2, 6]
		var action: String = ACTIONS[hand + (2 if hook else 0)]
		notes.append({"time": snappedf(time, 0.001), "action": action})
	if notes.size() < 4:
		return {"error": "Not enough rhythmic audio. Try a longer or more percussive song."}
	var chart_id := (song_id + "|" + VERSION + "|" + difficulty + "|" + str(bpm_override)).sha256_text()
	return {"id": chart_id, "song_id": song_id, "version": VERSION, "difficulty": difficulty,
		"bpm_override": bpm_override, "bpm": snappedf(bpm, 0.001), "confidence": analysis.confidence,
		"duration": duration, "beats": beats, "notes": notes, "sections": sections}


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
	if chart.get("beats") is not Array or chart.beats.is_empty():
		return false
	if absf(chart.beats.size() - duration * float(chart.bpm) / 60.0) > 2:
		return false
	var last_beat := -1.0
	for beat in chart.beats:
		if typeof(beat) not in [TYPE_INT, TYPE_FLOAT] or not is_finite(float(beat)):
			return false
		if float(beat) < 0 or float(beat) >= duration or float(beat) <= last_beat:
			return false
		last_beat = beat
	var previous := -10.0
	for note in chart.notes:
		if note is not Dictionary or note.get("action") not in ACTIONS:
			return false
		if typeof(note.get("time")) not in [TYPE_INT, TYPE_FLOAT]:
			return false
		var time := float(note.get("time", -1))
		if not is_finite(time) or time < 3.0 or time > duration - 0.4 or time - previous < 0.43:
			return false
		previous = time
	return true
