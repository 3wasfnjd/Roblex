-- Island Race: tuning values shared by server and client. No asset IDs, all prices in earned coins.
local Config = {}

Config.StartingCoins = 100
Config.CoinValue = 10          -- one track coin
Config.CoinRespawn = {8, 14}   -- seconds before a collected coin comes back

Config.Race = {
	Interval = 45,       -- free-roam seconds between races (waits longer if nobody joined)
	Countdown = 5,       -- seconds on the grid before "go"
	MaxDuration = 240,   -- race is ended after this many seconds
	ResultsTime = 12,    -- seconds the results stay up
	MaxRacers = 12,
}

Config.Rewards = {
	Place = {150, 100, 70},  -- 1st, 2nd, 3rd
	Other = 30,              -- every other finisher
	DNF = 10,                -- joined but did not finish
}

-- Vehicles: the player's own body is the "vehicle"; a board model is attached for the hoverboard.
Config.Vehicles = {
	{Id = "run",        Name = "جري",      Price = 0,   WalkSpeed = 22, JumpPower = 50, Glide = 0,   Desc = "اجرِ واقفز؛ متاح للجميع"},
	{Id = "hoverboard", Name = "هوفربورد", Price = 500, WalkSpeed = 34, JumpPower = 56, Glide = 0.5, Desc = "أسرع، وينزلق في الهواء فوق الفجوات"},
}
Config.VehicleById = {}
for _, v in ipairs(Config.Vehicles) do Config.VehicleById[v.Id] = v end

-- Upgrades apply per vehicle, three levels each.
Config.Upgrades = {
	{Key = "speed", Name = "السرعة", Prices = {150, 300, 600}, WalkSpeed = 2.5},
	{Key = "jump",  Name = "القفزة", Prices = {100, 200, 400}, JumpPower = 5},
}
Config.UpgradeByKey = {}
for _, u in ipairs(Config.Upgrades) do Config.UpgradeByKey[u.Key] = u end

Config.Boost = {Multiplier = 1.6, Duration = 3}   -- boost pads
Config.JumpPad = {Velocity = 78}                  -- applied on the client (player-owned character)
Config.FallY = -25                                -- below this the player is returned to the track
Config.DailyReward = {25, 50, 75, 100, 150, 200, 300}

Config.Tracks = {
	{Id = "Harbour", Name = "مسار الميناء", Laps = 2},
}
Config.TrackById = {}
for _, t in ipairs(Config.Tracks) do Config.TrackById[t.Id] = t end

return Config
