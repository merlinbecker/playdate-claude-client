-- Minimaler HTTP-Wrapper: genau eine Anfrage gleichzeitig, Antwort per Callback.
-- API gegen die aktuelle SDK-Doku prüfen (playdate.network.http, SDK 2.x).

Net = { busy = false, enabled = false, lastError = nil }

function Net.init()
  playdate.network.setEnabled(true, function(err)
    Net.enabled = (err == nil)
    Net.lastError = err
  end)
end

-- cb(ok, status, body)
function Net.request(method, path, body, cb)
  if Net.busy then return false end
  local conn, err = playdate.network.http.new(Config.server, Config.port, Config.ssl,
    "Sprachaufträge an deinen Assistenten senden und Antworten abholen")
  if not conn then
    Net.lastError = err
    cb(false, 0, nil)
    return true
  end
  Net.busy = true
  local headers = { ["X-Token"] = Config.token }
  local done = false
  local function finish(ok)
    if done then return end
    done = true
    local status = conn:getResponseStatus() or 0
    local n = conn:getBytesAvailable() or 0
    local data = n > 0 and conn:read(n) or ""
    conn:close()
    Net.busy = false
    cb(ok and status >= 200 and status < 300, status, data)
  end
  conn:setRequestCompleteCallback(function() finish(true) end)
  conn:setConnectionClosedCallback(function() finish(false) end)
  local ok, e
  if method == "GET" then
    ok, e = conn:get(path, headers)
  elseif method == "POST" then
    ok, e = conn:post(path, headers, body or "")
  else
    ok, e = conn:query(method, path, headers, body or "")
  end
  if not ok then
    Net.lastError = e
    done = true
    Net.busy = false
    cb(false, 0, nil)
  end
  return true
end
