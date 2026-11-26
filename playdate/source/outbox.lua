-- Store-and-forward: Aufnahmen und Interaktionen werden gespeichert und
-- bei Verbindung schrittweise hochgeladen. Überlebt App-Neustarts (datastore).

Outbox = { items = {}, retryAt = 0, backoff = 2, info = "" }

local CHUNK <const> = 8 * 1024

local function save() playdate.datastore.write(Outbox.items, "outbox") end

function Outbox.load()
  Outbox.items = playdate.datastore.read("outbox") or {}
end

function Outbox.addRecording(id, bytes, rate)
  local chunks = math.max(1, math.ceil(bytes / CHUNK))
  table.insert(Outbox.items, { kind = "rec", id = id, chunks = chunks, rate = rate, next = nil })
  save()
end

function Outbox.addChoice(cardId, value)
  local id = string.format("i%x%04x", playdate.getSecondsSinceEpoch(), math.random(0, 0xffff))
  table.insert(Outbox.items, { kind = "choice", id = id, card = cardId, value = value })
  save()
end

function Outbox.pending() return #Outbox.items end

local function fail()
  Outbox.retryAt = playdate.getCurrentTimeMilliseconds() + Outbox.backoff * 1000
  Outbox.backoff = math.min(Outbox.backoff * 2, 60)
  Outbox.info = "offline, neuer Versuch …"
end

local function success()
  Outbox.backoff = 2
end

local function readChunk(id, n)
  local f = playdate.file.open("rec/" .. id .. ".raw", playdate.file.kFileRead)
  if not f then return nil end
  f:seek(n * CHUNK)
  local d = f:read(CHUNK)
  f:close()
  return d
end

local function stepRecording(item)
  if item.next == nil then
    -- Server fragen, welche Chunks er schon hat (Wiederaufnahme)
    Net.request("GET", "/rec/" .. item.id, nil, function(ok, _, body)
      if not ok then return fail() end
      success()
      local res = json.decode(body) or {}
      if res.status and res.status ~= "uploading" then
        item.next = item.chunks -- schon fertig verarbeitet
      else
        local have = {}
        for _, n in ipairs(res.have or {}) do have[n] = true end
        item.next = 0
        while have[item.next] do item.next = item.next + 1 end
      end
      save()
    end)
  elseif item.next < item.chunks then
    local n = item.next
    Outbox.info = string.format("sende %d/%d", n + 1, item.chunks)
    Net.request("PUT", "/rec/" .. item.id .. "/chunk/" .. n, readChunk(item.id, n), function(ok)
      if not ok then return fail() end
      success()
      item.next = n + 1
      save()
    end)
  else
    local meta = json.encode({ rate = item.rate, chunks = item.chunks, signed = Config.signed })
    Net.request("POST", "/rec/" .. item.id .. "/done", meta, function(ok, status)
      if not ok and status ~= 409 then return fail() end
      success()
      if status == 409 then item.next = nil else -- Server fehlt etwas: neu abgleichen
        playdate.file.delete("rec/" .. item.id .. ".raw")
        table.remove(Outbox.items, 1)
        Outbox.info = "gesendet"
      end
      save()
    end)
  end
end

local function stepChoice(item)
  local body = json.encode({ id = item.id, card = item.card, value = item.value })
  Net.request("POST", "/interaction", body, function(ok)
    if not ok then return fail() end
    success()
    table.remove(Outbox.items, 1)
    save()
  end)
end

-- Wird jeden Frame aufgerufen; startet höchstens eine Anfrage.
function Outbox.update()
  if Net.busy or #Outbox.items == 0 then return end
  if playdate.getCurrentTimeMilliseconds() < Outbox.retryAt then return end
  local item = Outbox.items[1]
  if item.kind == "rec" then stepRecording(item) else stepChoice(item) end
end
