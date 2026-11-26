-- Kopieren nach config.lua und anpassen. config.lua wird nicht eingecheckt.
Config = {
  server = "192.168.1.20", -- IP oder Hostname des Servers
  port = 8000,
  ssl = false,             -- POC im LAN: false; VM mit HTTPS: true und port = 443
  token = "bitte-aendern", -- muss PDC_TOKEN auf dem Server entsprechen
  pollSeconds = 5,         -- Abstand der Inbox-Abfragen
  maxRecordSeconds = 30,
  step = 5,                -- Downsampling: jedes 5. Sample (44,1 kHz -> 8,8 kHz)
  signed = false,          -- auf true setzen, falls das WAV des Playdate signed 8 Bit liefert
}
