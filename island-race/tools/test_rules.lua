-- Unit tests for the pure rules. Run: python3 island-race/tools/run_tests.py
-- (the runner bundles Config and Rules into the globals Config and Rules, then runs this with the luau CLI)
local Config, Rules = Config, Rules
local passed, failed = 0, 0
local function check(name, cond)
	if cond then passed += 1 else failed += 1; print("FAIL: " .. name) end
end

local p = Rules.clean(nil, Config)
check("new profile coins", p.Coins == Config.StartingCoins)
check("new profile owns run", p.Vehicles.run == true and p.Equipped == "run")
check("upgrades initialised", p.Upgrades.run.speed == 0 and p.Upgrades.run.jump == 0)

local ok, why = Rules.buyVehicle(p, Config.VehicleById.hoverboard, Config)
check("cannot buy hoverboard with 100 coins", ok == false and why ~= nil)
p.Coins = 500
check("buy hoverboard", Rules.buyVehicle(p, Config.VehicleById.hoverboard, Config) == true and p.Coins == 0 and p.Equipped == "hoverboard")
check("cannot buy twice", Rules.buyVehicle(p, Config.VehicleById.hoverboard, Config) == false)
check("stats use hoverboard", Rules.stats(p, Config).WalkSpeed == 34 and Rules.stats(p, Config).Glide == 0.5)

p.Coins = 150
local ok2, lvl = Rules.upgrade(p, "hoverboard", "speed", Config)
check("upgrade speed level 1", ok2 == true and lvl == 1 and p.Coins == 0)
check("stats include upgrade", Rules.stats(p, Config).WalkSpeed == 36.5)
check("no coins for level 2", Rules.upgrade(p, "hoverboard", "speed", Config) == false)
p.Coins = 10000
Rules.upgrade(p, "hoverboard", "speed", Config); Rules.upgrade(p, "hoverboard", "speed", Config)
check("max level stops", Rules.upgrade(p, "hoverboard", "speed", Config) == false and p.Upgrades.hoverboard.speed == 3)
check("equip owned", Rules.equip(p, "run") == true and p.Equipped == "run")
check("equip unowned fails", Rules.equip(p, "jetpack") == false)

check("reward first", Rules.placementReward(1, true, Config) == 150)
check("reward fifth", Rules.placementReward(5, true, Config) == Config.Rewards.Other)
check("reward dnf", Rules.placementReward(0, false, Config) == Config.Rewards.DNF)

local d1 = Rules.dailyReward(p, 100, Config)
check("daily first day", d1 == Config.DailyReward[1] and p.Daily.Streak == 1)
check("daily same day nil", Rules.dailyReward(p, 100, Config) == nil)
local d2, s2 = Rules.dailyReward(p, 101, Config)
check("daily streak 2", d2 == Config.DailyReward[2] and s2 == 2)
local d3, s3 = Rules.dailyReward(p, 105, Config)
check("daily streak resets after a gap", d3 == Config.DailyReward[1] and s3 == 1)

check("record best first", Rules.recordResult(p, "Harbour", 95.5, 2) == true and p.BestTimes.Harbour == 95.5 and p.Wins == 0)
check("record slower not best", Rules.recordResult(p, "Harbour", 120, 1) == false and p.Wins == 1 and p.Races == 2)
check("record faster is best", Rules.recordResult(p, "Harbour", 80, 3) == true)

local snap = Rules.snapshot(p)
local back = Rules.clean(snap, Config)
check("roundtrip coins", back.Coins == p.Coins)
check("roundtrip vehicles", back.Vehicles.hoverboard == true and back.Upgrades.hoverboard.speed == 3)
check("roundtrip best", back.BestTimes.Harbour == 80 and back.Wins == 1 and back.Daily.Day == 105)
local dirty = Rules.clean({Coins = "abc", Vehicles = {jetpack = true, hoverboard = "yes"}, Equipped = "jetpack", BestTimes = {Harbour = -5, Nope = 3}, Upgrades = {run = {speed = 99}}}, Config)
check("dirty data cleaned", dirty.Coins == Config.StartingCoins and dirty.Vehicles.jetpack == nil and dirty.Equipped == "run" and dirty.BestTimes.Harbour == nil and dirty.Upgrades.run.speed == 3)

check("progress order", Rules.progress(2, 1, 5, 0) > Rules.progress(1, 5, 5, 0.9) and Rules.progress(1, 3, 5, 0.5) > Rules.progress(1, 3, 5, 0.1))
check("format time", Rules.formatTime(95.5) == "1:35.50" and Rules.formatTime(nil) == "—")

print(string.format("rules tests: %d passed, %d failed", passed, failed))
if failed > 0 then os.exit(1) end
