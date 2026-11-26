-- Holt neue Karten vom Server und hält einen lokalen Cache für die Offline-Ansicht.

Inbox = { cards = {}, since = 0, nextPoll = 0, onNew = nil }

local MAX_CARDS <const> = 30

function Inbox.load()
  local s = playdate.datastore.read("inbox") or {}
  Inbox.cards = s.cards or {}
  Inbox.since = s.since or 0
end

local function save()
  playdate.datastore.write({ cards = Inbox.cards, since = Inbox.since }, "inbox")
end

function Inbox.update()
  if Net.busy then return end
  local now = playdate.getCurrentTimeMilliseconds()
  if now < Inbox.nextPoll then return end
  Inbox.nextPoll = now + Config.pollSeconds * 1000
  Net.request("GET", "/inbox?since=" .. Inbox.since, nil, function(ok, _, body)
    if not ok then return end
    local res = json.decode(body)
    if not res or not res.cards then return end
    local added = 0
    for _, c in ipairs(res.cards) do
      table.insert(Inbox.cards, c)
      added = added + 1
    end
    while #Inbox.cards > MAX_CARDS do table.remove(Inbox.cards, 1) end
    Inbox.since = res.next or Inbox.since
    if added > 0 then
      save()
      if Inbox.onNew then Inbox.onNew(added) end
      if added >= 10 then Inbox.nextPoll = 0 end -- es gibt wohl noch mehr
    end
  end)
end
