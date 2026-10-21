-- Player profiles with a leased lock. Studio (or an unpublished place) uses temporary session data.
local DSS = game:GetService("DataStoreService")
local Http = game:GetService("HttpService")
local RunService = game:GetService("RunService")
local RS = game:GetService("ReplicatedStorage")
local Config = require(RS:WaitForChild("IslandRace"):WaitForChild("Config"))
local Rules = require(RS.IslandRace:WaitForChild("Rules"))

local Profiles = {}
Profiles.Live = {}

-- GetDataStore throws in a place that was never published; fall back to temporary session data then.
local storeCache
local function store()
	if storeCache == nil then
		local ok, s = pcall(function() return DSS:GetDataStore("IslandRace_v1") end)
		storeCache = ok and s or false
		if not ok then warn("[Island Race] DataStore unavailable (publish the place to save progress): " .. tostring(s)) end
	end
	return storeCache or nil
end

local function key(player) return "player_" .. player.UserId end
local function retry(fn)
	for attempt = 1, 3 do
		local ok, result = pcall(fn)
		if ok then return true, result end
		if attempt < 3 then task.wait(attempt * 1.5) end
	end
	return false
end

function Profiles.Load(player)
	local p
	local Store = store()
	if RunService:IsStudio() or game.GameId == 0 or not Store then
		p = Rules.clean(nil, Config)
		p.Temporary = true
	else
		local token = Http:GenerateGUID(false)
		local ok, raw = retry(function()
			return Store:UpdateAsync(key(player), function(old)
				old = type(old) == "table" and old or {}
				if type(old.Lock) == "table" and old.Lock.Token ~= token
					and (tonumber(old.Lock.Expires) or 0) > os.time() then return nil end
				local clean = Rules.clean(old, Config)
				clean.Lock = {Token = token, Expires = os.time() + 240}
				return clean
			end)
		end)
		if not ok or type(raw) ~= "table" or type(raw.Lock) ~= "table" or raw.Lock.Token ~= token then
			player:Kick("تعذر فتح بياناتك بأمان. انتظر قليلًا ثم ادخل مرة ثانية.")
			return nil
		end
		p = Rules.clean(raw, Config)
		p.Token = token
	end
	p.LastSave = os.clock()
	Profiles.Live[player] = p
	return p
end

function Profiles.Save(player, release)
	local p = Profiles.Live[player]
	if not p then return true end
	if p.Temporary then
		if release then Profiles.Live[player] = nil end
		return true
	end
	if release then p.Closing = true end
	while p.Saving do task.wait(0.05) end
	if Profiles.Live[player] ~= p then return true end
	p.Saving = true
	local copy = Rules.snapshot(p)
	local Store = store()
	if not Store then p.Saving = false; if release then Profiles.Live[player] = nil end; return false end
	local ok, result = retry(function()
		return Store:UpdateAsync(key(player), function(old)
			if type(old) ~= "table" or type(old.Lock) ~= "table" or old.Lock.Token ~= p.Token then return nil end
			if release then copy.Lock = nil else copy.Lock = {Token = p.Token, Expires = os.time() + 240} end
			return copy
		end)
	end)
	p.Saving = false
	if ok and result then p.LastSave = os.clock(); p.ReadOnly = false end
	if release then Profiles.Live[player] = nil end
	return ok and result ~= nil
end

function Profiles.Watchdog()
	for player, p in pairs(Profiles.Live) do
		if not p.Temporary and not p.Closing then
			local age = os.clock() - p.LastSave
			p.ReadOnly = age > 120
			if age > 200 then player:Kick("الاتصال بالحفظ متعطل. أعد الدخول لحماية تقدمك.") end
		end
	end
end

return Profiles
