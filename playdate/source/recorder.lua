-- Aufnahme und Downsampling. Ergebnis: rec/<id>.raw (8 Bit mono, ca. 8,8 kHz)
local snd <const> = playdate.sound

Recorder = { recording = false, processing = nil, startedAt = 0 }

local buffer = nil
local function newId()
  return string.format("%x%04x", playdate.getSecondsSinceEpoch(), math.random(0, 0xffff))
end

function Recorder.start()
  if Recorder.recording or Recorder.processing then return end
  buffer = snd.sample.new(Config.maxRecordSeconds, snd.kFormat8bitMono)
  Recorder.recording = true
  Recorder.startedAt = playdate.getCurrentTimeMilliseconds()
  snd.micinput.recordToSample(buffer, function(sample)
    Recorder.finish(sample)
  end)
end

function Recorder.stop()
  if Recorder.recording then
    snd.micinput.stopRecording() -- löst den Callback aus
  end
end

-- Läuft als Coroutine über mehrere Frames, damit die UI nicht einfriert.
function Recorder.finish(sample)
  Recorder.recording = false
  local id = newId()
  playdate.file.mkdir("rec")
  local wavPath = "rec/" .. id .. ".wav"
  sample:save(wavPath)
  Recorder.processing = coroutine.create(function()
    local f = playdate.file.open(wavPath, playdate.file.kFileRead)
    local size = playdate.file.getSize(wavPath)
    local data = f:read(size)
    f:close()
    local out = playdate.file.open("rec/" .. id .. ".raw", playdate.file.kFileWrite)
    local step, batch, count = Config.step, {}, 0
    -- Annahme: Standard-WAV-Header mit 44 Byte. Auf Hardware prüfen!
    for i = 45, #data, step do
      batch[#batch + 1] = string.byte(data, i)
      if #batch == 1000 then
        out:write(string.char(table.unpack(batch)))
        count = count + #batch
        batch = {}
        if count % 8000 == 0 then coroutine.yield() end
      end
    end
    if #batch > 0 then
      out:write(string.char(table.unpack(batch)))
      count = count + #batch
    end
    out:close()
    playdate.file.delete(wavPath)
    Outbox.addRecording(id, count, math.floor(44100 / step))
  end)
end

function Recorder.update()
  if Recorder.processing then
    local ok, err = coroutine.resume(Recorder.processing)
    if not ok then print("Recorder-Fehler: " .. tostring(err)) end
    if coroutine.status(Recorder.processing) == "dead" then Recorder.processing = nil end
  end
end

function Recorder.seconds()
  if not Recorder.recording then return 0 end
  return (playdate.getCurrentTimeMilliseconds() - Recorder.startedAt) / 1000
end
