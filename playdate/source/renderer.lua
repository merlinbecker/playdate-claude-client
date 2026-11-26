-- Generischer Renderer für die Karten-DSL (docs/karten-dsl.md).
local gfx <const> = playdate.graphics

Renderer = {}

local W <const>, H <const> = 400, 240
local HEADER <const>, FOOTER <const>, PAD <const> = 24, 20, 8
local GLYPHS <const> = { "i", "v", "x", "o", "f", "g", "@", "?" }
local KIND_TILE <const> = { status = 4, result = 2, question = 8, error = 3 }

local function icon(tile, x, y)
  gfx.drawRoundRect(x, y, 16, 16, 3)
  gfx.drawTextAligned(GLYPHS[tile] or "·", x + 8, y + 1, kTextAlignment.center)
end

-- Jede Funktion zeichnet ein Element ab y und gibt die neue Höhe zurück.
local draw = {}

function draw.text(e, y)
  local _, h = gfx.drawTextInRect(tostring(e.s or ""), PAD, y, W - 2 * PAD, 200)
  return y + math.max(h, 18) + 2
end

function draw.list(e, y)
  for i, item in ipairs(e.items or {}) do
    if i > 6 then break end
    gfx.fillCircleAtPoint(PAD + 3, y + 9, 2)
    gfx.drawText(tostring(item), PAD + 12, y)
    y = y + 20
  end
  return y
end

function draw.icon(e, y)
  icon(e.tile, PAD, y)
  return y + 20
end

function draw.bar(e, y)
  local v = math.max(0, math.min(1, tonumber(e.value) or 0))
  if e.label then gfx.drawText(tostring(e.label), PAD, y); y = y + 18 end
  gfx.drawRect(PAD, y, W - 2 * PAD, 10)
  gfx.fillRect(PAD + 2, y + 2, math.floor((W - 2 * PAD - 4) * v), 6)
  return y + 16
end

function draw.kv(e, y)
  gfx.drawText(tostring(e.k or ""), PAD, y)
  gfx.drawTextAligned("*" .. tostring(e.val or "") .. "*", W - PAD, y, kTextAlignment.right)
  return y + 20
end

function draw.sep(_, y)
  gfx.drawLine(PAD, y + 4, W - PAD, y + 4)
  return y + 10
end

-- card: Karte, state: {scroll, choice}, nav: {index, total, info}
function Renderer.draw(card, state, nav)
  gfx.clear(gfx.kColorWhite)
  if not card then
    gfx.drawTextAligned("*Halte A gedrückt und sprich*", W / 2, 100, kTextAlignment.center)
    gfx.drawTextAligned(nav.info or "", W / 2, 130, kTextAlignment.center)
    return
  end

  -- Inhalt (scrollbar per Kurbel)
  gfx.setClipRect(0, HEADER, W, H - HEADER - FOOTER)
  local y = HEADER + 6 - (state.scroll or 0)
  for _, e in ipairs(card.elements or {}) do
    local f = draw[e.t]
    if f then y = f(e, y) end -- unbekannte Typen überspringen
  end
  -- Auswahl
  local choices = card.choices or {}
  if #choices > 0 then
    y = y + 4
    for i, ch in ipairs(choices) do
      local label = tostring(ch.label)
      if i == state.choice then
        gfx.fillRoundRect(PAD, y, W - 2 * PAD, 20, 4)
        gfx.setImageDrawMode(gfx.kDrawModeFillWhite)
        gfx.drawText(label, PAD + 8, y + 2)
        gfx.setImageDrawMode(gfx.kDrawModeCopy)
      else
        gfx.drawRoundRect(PAD, y, W - 2 * PAD, 20, 4)
        gfx.drawText(label, PAD + 8, y + 2)
      end
      y = y + 24
    end
  end
  state.contentHeight = y + (state.scroll or 0) - HEADER
  gfx.clearClipRect()

  -- Kopfzeile
  gfx.fillRect(0, 0, W, HEADER)
  gfx.setImageDrawMode(gfx.kDrawModeFillWhite)
  gfx.drawText("*" .. tostring(card.title or "") .. "*", 28, 4)
  gfx.drawTextAligned(string.format("%d/%d", nav.index, nav.total), W - PAD, 4, kTextAlignment.right)
  gfx.setImageDrawMode(gfx.kDrawModeCopy)
  gfx.setColor(gfx.kColorWhite)
  gfx.fillRoundRect(5, 3, 18, 18, 3)
  gfx.setColor(gfx.kColorBlack)
  icon(KIND_TILE[card.kind] or 1, 6, 4)

  -- Fußzeile
  gfx.drawLine(0, H - FOOTER, W, H - FOOTER)
  gfx.drawText(nav.info or "", PAD, H - FOOTER + 2)
end
