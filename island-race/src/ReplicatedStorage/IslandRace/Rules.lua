-- Pure game rules (no engine calls) so they can be unit-tested with the luau CLI.
local Rules = {}

local function finite(n) return type(n) == "number" and n == n and math.abs(n) ~= math.huge end

function Rules.clean(raw, config)
	raw = type(raw) == "table" and raw or {}
	local coins = tonumber(raw.Coins)
	if not finite(coins) then coins = config.StartingCoins end
	local p = {
		Coins = math.clamp(math.floor(coins), 0, 10000000),
		Vehicles = {run = true},
		Equipped = "run",
		Upgrades = {},
		Wins = finite(tonumber(raw.Wins)) and math.max(0, math.floor(raw.Wins)) or 0,
		Races = finite(tonumber(raw.Races)) and math.max(0, math.floor(raw.Races)) or 0,
		BestTimes = {},
		Daily = {Day = 0, Streak = 0},
	}
	if type(raw.Vehicles) == "table" then
		for id, owned in pairs(raw.Vehicles) do
			if owned == true and config.VehicleById[id] then p.Vehicles[id] = true end
		end
	end
	if type(raw.Equipped) == "string" and p.Vehicles[raw.Equipped] then p.Equipped = raw.Equipped end
	for id in pairs(p.Vehicles) do
		p.Upgrades[id] = {}
		local src = type(raw.Upgrades) == "table" and type(raw.Upgrades[id]) == "table" and raw.Upgrades[id] or {}
		for _, u in ipairs(config.Upgrades) do
			local lvl = tonumber(src[u.Key])
			p.Upgrades[id][u.Key] = finite(lvl) and math.clamp(math.floor(lvl), 0, #u.Prices) or 0
		end
	end
	if type(raw.BestTimes) == "table" then
		for id, t in pairs(raw.BestTimes) do
			if config.TrackById[id] and finite(tonumber(t)) and t > 0 then p.BestTimes[id] = tonumber(t) end
		end
	end
	if type(raw.Daily) == "table" then
		local d, s = tonumber(raw.Daily.Day), tonumber(raw.Daily.Streak)
		if finite(d) and finite(s) then p.Daily = {Day = math.floor(d), Streak = math.clamp(math.floor(s), 0, 7)} end
	end
	return p
end

function Rules.snapshot(p)
	local out = {Coins = p.Coins, Vehicles = {}, Equipped = p.Equipped, Upgrades = {}, Wins = p.Wins, Races = p.Races,
		BestTimes = {}, Daily = {Day = p.Daily.Day, Streak = p.Daily.Streak}}
	for id, v in pairs(p.Vehicles) do out.Vehicles[id] = v end
	for id, levels in pairs(p.Upgrades) do
		out.Upgrades[id] = {}
		for k, v in pairs(levels) do out.Upgrades[id][k] = v end
	end
	for id, t in pairs(p.BestTimes) do out.BestTimes[id] = t end
	return out
end

function Rules.buyVehicle(p, vehicle, config)
	if not vehicle then return false, "مركبة غير موجودة" end
	if p.Vehicles[vehicle.Id] then return false, "تملكها بالفعل" end
	if p.Coins < vehicle.Price then return false, "عملاتك لا تكفي؛ اجمع عملات المسار أو فز بسباق" end
	p.Coins = p.Coins - vehicle.Price
	p.Vehicles[vehicle.Id] = true
	p.Upgrades[vehicle.Id] = {}
	for _, u in ipairs(config.Upgrades) do p.Upgrades[vehicle.Id][u.Key] = 0 end
	p.Equipped = vehicle.Id
	return true
end

function Rules.equip(p, vehicleId)
	if not p.Vehicles[vehicleId] then return false, "لا تملك هذه المركبة" end
	p.Equipped = vehicleId
	return true
end

function Rules.upgrade(p, vehicleId, key, config)
	local u = config.UpgradeByKey[key]
	if not u or not p.Vehicles[vehicleId] then return false, "ترقية غير متاحة" end
	local level = p.Upgrades[vehicleId][key] or 0
	if level >= #u.Prices then return false, "وصلت للمستوى الأقصى" end
	local price = u.Prices[level + 1]
	if p.Coins < price then return false, "عملاتك لا تكفي" end
	p.Coins = p.Coins - price
	p.Upgrades[vehicleId][key] = level + 1
	return true, level + 1
end

-- Movement numbers for the equipped vehicle with its upgrades applied.
function Rules.stats(p, config)
	local v = config.VehicleById[p.Equipped] or config.Vehicles[1]
	local s = {WalkSpeed = v.WalkSpeed, JumpPower = v.JumpPower, Glide = v.Glide, Vehicle = v.Id}
	local levels = p.Upgrades[v.Id] or {}
	for _, u in ipairs(config.Upgrades) do
		local lvl = levels[u.Key] or 0
		if u.WalkSpeed then s.WalkSpeed = s.WalkSpeed + u.WalkSpeed * lvl end
		if u.JumpPower then s.JumpPower = s.JumpPower + u.JumpPower * lvl end
	end
	return s
end

function Rules.placementReward(place, finished, config)
	if not finished then return config.Rewards.DNF end
	return config.Rewards.Place[place] or config.Rewards.Other
end

-- day = whole days since the epoch. Returns the reward for today, or nil if already claimed.
function Rules.dailyReward(p, day, config)
	if p.Daily.Day == day then return nil end
	local streak = (p.Daily.Day == day - 1) and math.min(7, p.Daily.Streak + 1) or 1
	p.Daily = {Day = day, Streak = streak}
	local amount = config.DailyReward[streak] or config.DailyReward[#config.DailyReward]
	p.Coins = math.min(10000000, p.Coins + amount)
	return amount, streak
end

-- Records a finished race. Returns true when the time is a new personal best.
function Rules.recordResult(p, trackId, seconds, place)
	p.Races = p.Races + 1
	if place == 1 then p.Wins = p.Wins + 1 end
	local best = p.BestTimes[trackId]
	if not best or seconds < best then p.BestTimes[trackId] = seconds; return true end
	return false
end

-- Race progress used for live ranking: laps and checkpoints passed plus the fraction toward the next one.
function Rules.progress(lap, nextCheckpoint, checkpointCount, fraction)
	return (lap - 1) * checkpointCount + (nextCheckpoint - 1) + math.clamp(fraction or 0, 0, 0.999)
end

function Rules.formatTime(seconds)
	if not seconds then return "—" end
	local m = math.floor(seconds / 60)
	local s = seconds - m * 60
	return string.format("%d:%05.2f", m, s)
end

return Rules
