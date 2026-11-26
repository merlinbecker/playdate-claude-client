-- playdate-claude-client
-- A halten = sprechen, A tippen = Auswahl bestätigen,
-- ◀ ▶ = Karten blättern, ▲ ▼ = Auswahl, Kurbel = scrollen.

import "CoreLibs/graphics"
import "CoreLibs/timer"
import "config"
import "net"
import "recorder"
import "outbox"
import "inbox"
import "renderer"

local HOLD_MS <const> = 250

local index = 0           -- aktuell angezeigte Karte (0 = keine)
local state = { scroll = 0, choice = 1 }
local holdTimer = nil

local function current() return Inbox.cards[index] end

local function show(i)
  index = math.max(1, math.min(i, #Inbox.cards))
  state = { scroll = 0, choice = 1 }
end

Inbox.onNew = function()
  show(#Inbox.cards) -- neueste Karte anzeigen
  playdate.sound.synth.new(playdate.sound.kWaveSine):playNote(880, 0.3, 0.08)
end

function playdate.AButtonDown()
  holdTimer = playdate.timer.performAfterDelay(HOLD_MS, function()
    holdTimer = nil
    Recorder.start()
  end)
end

function playdate.AButtonUp()
  if holdTimer then -- kurzer Tipp: Auswahl bestätigen
    holdTimer:remove()
    holdTimer = nil
    local c = current()
    if c and c.choices and c.choices[state.choice] then
      Outbox.addChoice(c.id, c.choices[state.choice].value)
    end
  else
    Recorder.stop()
  end
end

function playdate.leftButtonDown() show(index - 1) end
function playdate.rightButtonDown() show(index + 1) end
function playdate.upButtonDown() state.choice = math.max(1, state.choice - 1) end
function playdate.downButtonDown()
  local c = current()
  state.choice = math.min(state.choice + 1, math.max(1, c and c.choices and #c.choices or 1))
end

local function footer()
  if Recorder.recording then return string.format("● Aufnahme %.1f s", Recorder.seconds()) end
  if Recorder.processing then return "verarbeite Aufnahme …" end
  if Outbox.pending() > 0 then return string.format("%d ausstehend · %s", Outbox.pending(), Outbox.info) end
  if not Net.enabled then return "kein Netz" end
  return "bereit"
end

local function init()
  math.randomseed(playdate.getSecondsSinceEpoch())
  Outbox.load()
  Inbox.load()
  if #Inbox.cards > 0 then show(#Inbox.cards) end
  Net.init()
end

function playdate.update()
  playdate.timer.updateTimers()
  Recorder.update()
  if not Recorder.recording then
    Outbox.update()
    Inbox.update()
  end
  local max = math.max(0, (state.contentHeight or 0) - 190)
  state.scroll = math.max(0, math.min(max, state.scroll + playdate.getCrankChange()))
  Renderer.draw(current(), state, { index = index, total = #Inbox.cards, info = footer() })
end

init()
