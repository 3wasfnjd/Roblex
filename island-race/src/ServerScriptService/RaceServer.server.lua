-- Island Race: race loop, economy, vehicles, coins, boost pads, fall guard, leaderboards.
-- Everything that gives coins or decides a race happens here, from server-observed positions.
local Players = game:GetService("Players")
local RS = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local shared = RS:WaitForChild("IslandRace")
local Config = require(shared:WaitForChild("Config"))
local Rules = require(shared:WaitForChild("Rules"))
local Profiles = require(script.Parent:WaitForChild("ProfileStore"))

local map = workspace:WaitForChild("IslandRace")
local lobby = map:WaitForChild("Lobby")
local tracksFolder = map:WaitForChild("Tracks")

-- ---------------------------------------------------------------- remotes
local rem = shared:FindFirstChild("Remotes")
if not rem then rem = Instance.new("Folder"); rem.Name = "Remotes"; rem.Parent = shared end
local function remote(name)
	local r = rem:FindFirstChild(name)
	if not r then r = Instance.new("RemoteEvent"); r.Name = name; r.Parent = rem end
	return r
end
local StateRemote, ActionRemote, NoticeRemote, RaceRemote = remote("State"), remote("Action"), remote("Notice"), remote("Race")

-- ---------------------------------------------------------------- helpers
local cooldown = {}
local function allow(player, key, seconds)
	local now = os.clock(); cooldown[player] = cooldown[player] or {}
	if now < (cooldown[player][key] or 0) then return false end
	cooldown[player][key] = now + seconds; return true
end
local function body(player)
	local c = player.Character
	local h = c and c:FindFirstChildOfClass("Humanoid")
	local r = c and c:FindFirstChild("HumanoidRootPart")
	if c and h and r and h.Health > 0 then return c, h, r end
	return nil
end
local function active(player)
	local p = Profiles.Live[player]
	return p and not p.ReadOnly and not p.Closing and p or nil
end
local function notice(player, text, kind, data)
	if player.Parent == Players then NoticeRemote:FireClient(player, text, kind, data) end
end
local function playerFromHit(hit)
	local model = hit and hit:FindFirstAncestorOfClass("Model")
	return model and Players:GetPlayerFromCharacter(model) or nil
end
local function today() return math.floor(os.time() / 86400) end

-- ---------------------------------------------------------------- race state
local track = tracksFolder:WaitForChild(Config.Tracks[1].Id)
local trackDef = Config.Tracks[1]
local startLine = track:WaitForChild("StartLine")
local gridSlots = track:WaitForChild("Grid"):GetChildren()
table.sort(gridSlots, function(a, b) return a.Name < b.Name end)
local checkpoints = track:WaitForChild("Checkpoints"):GetChildren()
table.sort(checkpoints, function(a, b) return tonumber(a.Name:match("%d+")) < tonumber(b.Name:match("%d+")) end)
-- the start line is the last checkpoint of every lap
table.insert(checkpoints, startLine)
local CP = #checkpoints

local race = {Phase = "Idle", Deadline = 0, Joined = {}, Racers = {}, StartedAt = 0, Round = 0}
local lastCheckpoint = {}   -- player -> CFrame to return to after a fall

local function joinedIds()
	local out = {}
	for pl in pairs(race.Joined) do table.insert(out, pl.UserId) end
	return out
end

-- ---------------------------------------------------------------- player state
local boostUntil = {}
local function stats(player)
	local p = Profiles.Live[player]
	return p and Rules.stats(p, Config) or Rules.stats(Rules.clean(nil, Config), Config)
end
local function removeBoard(char)
	local old = char:FindFirstChild("Hoverboard")
	if old then old:Destroy() end
end
local function attachBoard(player, char, root)
	removeBoard(char)
	local board = Instance.new("Model"); board.Name = "Hoverboard"
	local deck = Instance.new("Part"); deck.Name = "Deck"; deck.Size = Vector3.new(2.4, 0.3, 5.2)
	deck.Color = Color3.fromRGB(40, 110, 240); deck.Material = Enum.Material.SmoothPlastic
	deck.CanCollide = false; deck.CanTouch = false; deck.CanQuery = false; deck.Massless = true; deck.Anchored = false
	deck.CFrame = root.CFrame * CFrame.new(0, -3.05, 0); deck.Parent = board
	local stripe = deck:Clone(); stripe.Name = "Stripe"; stripe.Size = Vector3.new(0.6, 0.32, 4.6)
	stripe.Color = Color3.fromRGB(255, 150, 40); stripe.Material = Enum.Material.Neon; stripe.Parent = board
	for _, part in ipairs({deck, stripe}) do
		local w = Instance.new("WeldConstraint"); w.Part0 = root; w.Part1 = part; w.Parent = part
	end
	local a0 = Instance.new("Attachment"); a0.Position = Vector3.new(-1.1, 0, 2.4); a0.Parent = deck
	local a1 = Instance.new("Attachment"); a1.Position = Vector3.new(1.1, 0, 2.4); a1.Parent = deck
	local trail = Instance.new("Trail"); trail.Attachment0 = a0; trail.Attachment1 = a1
	trail.Color = ColorSequence.new(Color3.fromRGB(90, 190, 255), Color3.fromRGB(255, 150, 40))
	trail.Transparency = NumberSequence.new({NumberSequenceKeypoint.new(0, 0.3), NumberSequenceKeypoint.new(1, 1)})
	trail.Lifetime = 0.5; trail.LightEmission = 0.8; trail.MinLength = 0.2; trail.Parent = deck
	board.Parent = char
end
local function applyStats(player)
	local char, hum, root = body(player)
	if not char then return end
	local s = stats(player)
	local boosted = (boostUntil[player] or 0) > os.clock()
	local frozen = char:GetAttribute("Frozen") == true
	hum.WalkSpeed = frozen and 0 or (s.WalkSpeed * (boosted and Config.Boost.Multiplier or 1))
	hum.JumpPower = frozen and 0 or s.JumpPower
	hum.UseJumpPower = true
	char:SetAttribute("Glide", s.Glide)
	char:SetAttribute("Vehicle", s.Vehicle)
	if s.Vehicle == "hoverboard" then
		if not char:FindFirstChild("Hoverboard") then attachBoard(player, char, root) end
	else
		removeBoard(char)
	end
end
local function freeze(player, on)
	local char = body(player)
	if char then char:SetAttribute("Frozen", on); applyStats(player) end
end

local function send(player)
	local p = Profiles.Live[player]
	if not p or player.Parent ~= Players then return end
	StateRemote:FireClient(player, {
		Coins = p.Coins, Vehicles = p.Vehicles, Equipped = p.Equipped, Upgrades = p.Upgrades,
		Wins = p.Wins, Races = p.Races, BestTimes = p.BestTimes,
		Temporary = p.Temporary or false, ReadOnly = p.ReadOnly or false,
		Race = {Phase = race.Phase, Deadline = race.Deadline, Joined = joinedIds(), Track = trackDef.Name, Laps = trackDef.Laps, Round = race.Round},
	})
	local leader = player:FindFirstChild("leaderstats")
	if leader then
		leader.Coins.Value = p.Coins
		leader.Wins.Value = p.Wins
	end
end
local function broadcast() for _, pl in ipairs(Players:GetPlayers()) do send(pl) end end
local function award(player, amount, why)
	local p = active(player)
	if not p or amount <= 0 then return end
	p.Coins = math.min(10000000, p.Coins + amount)
	send(player)
end

-- ---------------------------------------------------------------- leaderboards (OrderedDataStore)
local Leaderboard = {}
do
	local DSS = game:GetService("DataStoreService")
	local bestStore, winStore
	pcall(function()
		bestStore = DSS:GetOrderedDataStore("IR_Best_" .. trackDef.Id .. "_v1")
		winStore = DSS:GetOrderedDataStore("IR_Wins_v1")
	end)
	local cloud = bestStore ~= nil and not RunService:IsStudio()
	local sessionBest, sessionWins, names = {}, {}, {}
	function Leaderboard.recordBest(player, seconds)
		names[player.UserId] = player.DisplayName
		local ms = math.floor(seconds * 1000)
		if not sessionBest[player.UserId] or ms < sessionBest[player.UserId] then sessionBest[player.UserId] = ms end
		if cloud then task.spawn(function()
			pcall(function()
				bestStore:UpdateAsync(tostring(player.UserId), function(old)
					if type(old) == "number" and old <= ms then return nil end
					return ms
				end)
			end)
		end) end
	end
	function Leaderboard.recordWin(player)
		names[player.UserId] = player.DisplayName
		sessionWins[player.UserId] = (sessionWins[player.UserId] or 0) + 1
		if cloud then task.spawn(function() pcall(function() winStore:IncrementAsync(tostring(player.UserId), 1) end) end) end
	end
	local function top(store, session, ascending)
		local list = {}
		if cloud then
			local ok, page = pcall(function() return store:GetSortedAsync(ascending, 10):GetCurrentPage() end)
			if ok and page then
				for _, e in ipairs(page) do
					local uid = tonumber(e.key)
					if uid then table.insert(list, {uid = uid, value = e.value}) end
				end
				return list, true
			end
		end
		for uid, v in pairs(session) do table.insert(list, {uid = uid, value = v}) end
		table.sort(list, function(a, b) if ascending then return a.value < b.value end return a.value > b.value end)
		while #list > 10 do table.remove(list) end
		return list, false
	end
	local function lookup(ids)
		local missing = {}
		for _, uid in ipairs(ids) do if not names[uid] then table.insert(missing, uid) end end
		if #missing > 0 then
			local ok, infos = pcall(function() return game:GetService("UserService"):GetUserInfosByUserIdsAsync(missing) end)
			if ok and infos then for _, info in ipairs(infos) do names[info.Id] = info.DisplayName end end
			for _, uid in ipairs(missing) do names[uid] = names[uid] or "لاعب" end
		end
	end
	-- board surface
	local face = lobby:FindFirstChild("Board")
	local rows = {}
	if face then
		local gui = Instance.new("SurfaceGui"); gui.Name = "Board"; gui.Face = Enum.NormalId.Front
		gui.SizingMode = Enum.SurfaceGuiSizingMode.PixelsPerStud; gui.PixelsPerStud = 40; gui.LightInfluence = 0; gui.Brightness = 1.3; gui.Parent = face
		local NAVY, BLUE, ORANGE = Color3.fromRGB(22, 30, 60), Color3.fromRGB(90, 190, 255), Color3.fromRGB(255, 150, 40)
		local function text(parent, x, y, w, h, size, color, str, align)
			local t = Instance.new("TextLabel"); t.BackgroundTransparency = 1; t.Position = UDim2.fromScale(x, y); t.Size = UDim2.fromScale(w, h)
			t.TextScaled = true; t.Font = Enum.Font.GothamBold; t.TextColor3 = color; t.Text = str or ""; t.Parent = parent
			t.TextXAlignment = align or Enum.TextXAlignment.Center
			local c = Instance.new("UITextSizeConstraint"); c.MaxTextSize = size; c.Parent = t
			return t
		end
		text(gui, 0.05, 0.02, 0.9, 0.12, 110, Color3.new(1, 1, 1), "🏁 لوحة المتصدرين")
		local function column(x, title)
			local frame = Instance.new("Frame"); frame.BackgroundColor3 = NAVY; frame.BackgroundTransparency = 0.15; frame.BorderSizePixel = 0
			frame.Position = UDim2.fromScale(x, 0.16); frame.Size = UDim2.fromScale(0.455, 0.8); frame.Parent = gui
			local corner = Instance.new("UICorner"); corner.CornerRadius = UDim.new(0.04, 0); corner.Parent = frame
			text(frame, 0.04, 0.01, 0.92, 0.1, 60, ORANGE, title)
			local list = {}
			for i = 1, 10 do
				local y = 0.12 + (i - 1) * 0.087
				local rank = text(frame, 0.84, y, 0.13, 0.08, 44, BLUE, ({"🥇", "🥈", "🥉"})[i] or tostring(i))
				local name = text(frame, 0.26, y, 0.57, 0.08, 42, Color3.new(1, 1, 1), "—", Enum.TextXAlignment.Right)
				local val = text(frame, 0.03, y, 0.23, 0.08, 42, BLUE, "", Enum.TextXAlignment.Left)
				list[i] = {rank, name, val}
			end
			return list
		end
		rows.best = column(0.525, "⏱ أسرع زمن • " .. trackDef.Name)
		rows.wins = column(0.02, "🏆 أكثر فوزًا")
	end
	local function fill(list, entries, fmt)
		for i, row in ipairs(list) do
			local e = entries[i]
			row[2].Text = e and (names[e.uid] or "لاعب") or "—"
			row[3].Text = e and fmt(e.value) or ""
		end
	end
	function Leaderboard.refresh()
		if not face then return end
		local best = top(bestStore, sessionBest, true)
		local wins = top(winStore, sessionWins, false)
		local ids = {}
		for _, e in ipairs(best) do table.insert(ids, e.uid) end
		for _, e in ipairs(wins) do table.insert(ids, e.uid) end
		lookup(ids)
		fill(rows.best, best, function(ms) return Rules.formatTime(ms / 1000) end)
		fill(rows.wins, wins, function(n) return tostring(n) end)
	end
	task.spawn(function()
		task.wait(3)
		while true do
			local ok, err = pcall(Leaderboard.refresh)
			if not ok then warn("[Island Race] leaderboard: " .. tostring(err)) end
			task.wait(60)
		end
	end)
end

-- ---------------------------------------------------------------- lobby sign
local signLabel
do
	local sign = lobby:FindFirstChild("Sign")
	if sign then
		local gui = Instance.new("SurfaceGui"); gui.Face = Enum.NormalId.Front; gui.SizingMode = Enum.SurfaceGuiSizingMode.PixelsPerStud
		gui.PixelsPerStud = 40; gui.LightInfluence = 0; gui.Parent = sign
		signLabel = Instance.new("TextLabel"); signLabel.BackgroundTransparency = 1; signLabel.Size = UDim2.fromScale(0.94, 0.9); signLabel.Position = UDim2.fromScale(0.03, 0.05)
		signLabel.TextScaled = true; signLabel.Font = Enum.Font.GothamBlack; signLabel.TextColor3 = Color3.new(1, 1, 1); signLabel.Text = ""; signLabel.Parent = gui
		local c = Instance.new("UITextSizeConstraint"); c.MaxTextSize = 70; c.Parent = signLabel
	end
end
local function setSign(text) if signLabel then signLabel.Text = text end end

-- ---------------------------------------------------------------- checkpoints
local function insideBox(part, pos)
	local rel = part.CFrame:PointToObjectSpace(pos)
	local h = part.Size / 2
	return math.abs(rel.X) <= h.X and math.abs(rel.Y) <= h.Y + 2 and math.abs(rel.Z) <= h.Z
end
local function returnPoint(player)
	return lastCheckpoint[player] or (lobby:FindFirstChild("Spawn") and lobby.Spawn.CFrame + Vector3.new(0, 4, 0)) or CFrame.new(0, 10, 0)
end
local function teleport(player, cf)
	local char, _, root = body(player)
	if not char then return end
	root.AssemblyLinearVelocity = Vector3.zero
	char:PivotTo(cf)
end

-- ---------------------------------------------------------------- race phases
local function setPhase(phase, deadline)
	race.Phase = phase; race.Deadline = deadline or 0
	RaceRemote:FireAllClients("phase", {Phase = phase, Deadline = race.Deadline, Joined = joinedIds(), Track = trackDef.Name, Laps = trackDef.Laps, Round = race.Round})
	broadcast()
end
local function racerList()
	local list = {}
	for pl, r in pairs(race.Racers) do table.insert(list, {Player = pl, R = r}) end
	table.sort(list, function(a, b)
		if a.R.Finished and b.R.Finished then return a.R.Time < b.R.Time end
		if a.R.Finished ~= b.R.Finished then return a.R.Finished end
		return a.R.Progress > b.R.Progress
	end)
	return list
end
local function tick()
	local order = {}
	for i, e in ipairs(racerList()) do
		table.insert(order, {UserId = e.Player.UserId, Name = e.Player.DisplayName, Lap = e.R.Lap, Finished = e.R.Finished, Time = e.R.Time, Place = i})
	end
	RaceRemote:FireAllClients("tick", {Order = order, Elapsed = os.clock() - race.StartedAt, Laps = trackDef.Laps})
end
local function updateRacer(player, r)
	local char, _, root = body(player)
	if not char then return end
	local pos = root.Position
	local cp = checkpoints[r.NextCP]
	if insideBox(cp, pos) then
		lastCheckpoint[player] = cp.CFrame * CFrame.new(0, 0, 0) + Vector3.new(0, 4, 0)
		if r.NextCP == CP then
			if r.Lap >= trackDef.Laps then
				r.Finished = true; r.Time = os.clock() - race.StartedAt; r.Progress = math.huge
				notice(player, "وصلت! زمنك " .. Rules.formatTime(r.Time), "Finish")
				return
			end
			r.Lap = r.Lap + 1; r.NextCP = 1
			notice(player, "اللفة " .. r.Lap .. " من " .. trackDef.Laps, "Lap")
		else
			r.NextCP = r.NextCP + 1
		end
	end
	local nextPos = checkpoints[r.NextCP].Position
	local prevPos = (r.NextCP == 1 and startLine or checkpoints[r.NextCP - 1]).Position
	local seg = (nextPos - prevPos).Magnitude
	local fraction = seg > 0 and (1 - (nextPos - pos).Magnitude / seg) or 0
	r.Progress = Rules.progress(r.Lap, r.NextCP, CP, fraction)
end

local function runRace()
	race.Round = race.Round + 1
	-- grid
	race.Racers = {}
	local i = 0
	for pl in pairs(race.Joined) do
		if body(pl) and active(pl) then
			i = i + 1
			local slot = gridSlots[((i - 1) % #gridSlots) + 1]
			local row = math.floor((i - 1) / #gridSlots)
			teleport(pl, slot.CFrame * CFrame.new(0, 3, row * 6))
			freeze(pl, true)
			lastCheckpoint[pl] = slot.CFrame + Vector3.new(0, 4, 0)
			race.Racers[pl] = {Lap = 1, NextCP = 1, Finished = false, Time = nil, Progress = 0}
		end
	end
	if i == 0 then race.Joined = {}; return end
	setPhase("Countdown", workspace:GetServerTimeNow() + Config.Race.Countdown)
	setSign("استعدوا!")
	task.wait(Config.Race.Countdown)
	-- go
	race.StartedAt = os.clock()
	for pl in pairs(race.Racers) do freeze(pl, false); notice(pl, "انطلق! 🏁", "Go") end
	setPhase("Racing", workspace:GetServerTimeNow() + Config.Race.MaxDuration)
	setSign("السباق جارٍ")
	local lastTick = 0
	while true do
		task.wait(0.1)
		local running = 0
		for pl, r in pairs(race.Racers) do
			if pl.Parent ~= Players then race.Racers[pl] = nil
			elseif not r.Finished then running = running + 1; updateRacer(pl, r) end
		end
		if os.clock() - lastTick >= 0.5 then lastTick = os.clock(); tick() end
		if running == 0 or os.clock() - race.StartedAt > Config.Race.MaxDuration then break end
	end
	-- results
	local results = {}
	for i2, e in ipairs(racerList()) do
		local pl, r = e.Player, e.R
		local place = r.Finished and i2 or 0
		local reward = Rules.placementReward(place, r.Finished, Config)
		local p = active(pl)
		local newBest = false
		if p then
			if r.Finished then
				newBest = Rules.recordResult(p, trackDef.Id, r.Time, place)
				Leaderboard.recordBest(pl, r.Time)
				if place == 1 then Leaderboard.recordWin(pl) end
			end
			award(pl, reward)
		end
		table.insert(results, {UserId = pl.UserId, Name = pl.DisplayName, Time = r.Time, Place = place, Reward = reward, NewBest = newBest, Finished = r.Finished})
		notice(pl, r.Finished and ("المركز " .. place .. " • +" .. reward .. " عملة" .. (newBest and " • رقم شخصي جديد!" or "")) or ("لم تكمل السباق • +" .. reward), r.Finished and place == 1 and "Win" or "Result")
		freeze(pl, false)
	end
	if results[1] and results[1].Finished then setSign("الفائز: " .. results[1].Name .. " 🏆") else setSign("انتهى السباق") end
	race.Joined = {}; race.Racers = {}
	setPhase("Results", workspace:GetServerTimeNow() + Config.Race.ResultsTime)
	RaceRemote:FireAllClients("results", {List = results, Track = trackDef.Name})
	task.wait(Config.Race.ResultsTime)
	for pl in pairs(lastCheckpoint) do lastCheckpoint[pl] = nil end
end

task.spawn(function()
	while true do
		setPhase("Idle", workspace:GetServerTimeNow() + Config.Race.Interval)
		while true do
			local left = race.Deadline - workspace:GetServerTimeNow()
			local n = #joinedIds()
			setSign(n > 0 and string.format("السباق يبدأ خلال %d ث • %d مسجّل", math.max(0, math.ceil(left)), n) or "اضغط «انضم» لبدء السباق")
			if left <= 0 then
				if n > 0 then break end
				race.Deadline = workspace:GetServerTimeNow() + 15   -- keep waiting until someone joins
			end
			task.wait(1)
		end
		local ok, err = pcall(runRace)
		if not ok then
			warn("[Island Race] race error: " .. tostring(err))
			for pl in pairs(race.Racers) do freeze(pl, false) end
			race.Joined = {}; race.Racers = {}
		end
	end
end)

local function toggleJoin(player)
	if not active(player) or not body(player) then return end
	if race.Phase ~= "Idle" then notice(player, "السباق بدأ؛ سجّل في الجولة القادمة"); return end
	if race.Joined[player] then
		race.Joined[player] = nil; notice(player, "خرجت من قائمة السباق")
	else
		if #joinedIds() >= Config.Race.MaxRacers then notice(player, "السباق ممتلئ"); return end
		race.Joined[player] = true; notice(player, "تم التسجيل! السباق يبدأ قريبًا", "Joined")
		if race.Deadline - workspace:GetServerTimeNow() > 20 and #joinedIds() == 1 then
			race.Deadline = workspace:GetServerTimeNow() + 20   -- first joiner shortens the wait
		end
	end
	setPhase(race.Phase, race.Deadline)
end
local joinPoint = lobby:FindFirstChild("JoinPoint")
if joinPoint then
	local prompt = joinPoint:FindFirstChildOfClass("ProximityPrompt") or Instance.new("ProximityPrompt", joinPoint)
	prompt.ActionText = "انضم للسباق"; prompt.ObjectText = "بوابة السباق"; prompt.HoldDuration = 0; prompt.MaxActivationDistance = 10; prompt.RequiresLineOfSight = false
	prompt.Triggered:Connect(function(pl) if allow(pl, "join", 0.5) then toggleJoin(pl) end end)
end
local shopPoint = lobby:FindFirstChild("ShopPoint")
if shopPoint then
	local prompt = shopPoint:FindFirstChildOfClass("ProximityPrompt") or Instance.new("ProximityPrompt", shopPoint)
	prompt.ActionText = "افتح المتجر"; prompt.ObjectText = "كراج المركبات"; prompt.HoldDuration = 0; prompt.MaxActivationDistance = 10; prompt.RequiresLineOfSight = false
	prompt.Triggered:Connect(function(pl) if active(pl) and allow(pl, "shop", 0.3) then notice(pl, "", "Shop") end end)
end

-- ---------------------------------------------------------------- actions from the client
ActionRemote.OnServerEvent:Connect(function(player, action, arg, arg2)
	if type(action) ~= "string" or not allow(player, "network", 0.08) then return end
	if action == "sync" then send(player); return end
	local p = active(player)
	if not p then return end
	if action == "join" then
		toggleJoin(player)
	elseif action == "buy" then
		local ok, why = Rules.buyVehicle(p, type(arg) == "string" and Config.VehicleById[arg] or nil, Config)
		if ok then applyStats(player); notice(player, "اشتريت " .. Config.VehicleById[arg].Name .. " وتم تجهيزها", "Buy") else notice(player, why) end
		send(player)
	elseif action == "equip" then
		if type(arg) ~= "string" then return end
		local ok, why = Rules.equip(p, arg)
		if ok then applyStats(player) else notice(player, why) end
		send(player)
	elseif action == "upgrade" then
		if type(arg) ~= "string" or type(arg2) ~= "string" then return end
		local ok, result = Rules.upgrade(p, arg, arg2, Config)
		if ok then applyStats(player); notice(player, Config.UpgradeByKey[arg2].Name .. " مستوى " .. result, "Buy") else notice(player, result) end
		send(player)
	end
end)

-- ---------------------------------------------------------------- track coins
do
	local markers = track:FindFirstChild("Coins") and track.Coins:GetChildren() or {}
	local coins = {}
	local template = shared:FindFirstChild("Templates") and shared.Templates:FindFirstChild("Coin")
	for _, m in ipairs(markers) do
		local c
		if template then
			c = template:Clone(); c.Name = "Coin"; c.Anchored = true; c.CanCollide = false; c.CanTouch = false; c.CanQuery = false
			c.CFrame = CFrame.new(m.Position)
		else
			c = Instance.new("Part"); c.Name = "Coin"; c.Shape = Enum.PartType.Cylinder; c.Size = Vector3.new(0.3, 2, 2)
			c.Material = Enum.Material.Neon; c.Color = Color3.fromRGB(255, 205, 60); c.Anchored = true; c.CanCollide = false; c.CanTouch = false; c.CanQuery = false
			c.CFrame = CFrame.new(m.Position) * CFrame.Angles(0, 0, math.pi / 2)
		end
		local glow = Instance.new("PointLight"); glow.Color = Color3.fromRGB(255, 205, 60); glow.Range = 7; glow.Brightness = 0.8; glow.Parent = c
		c.Parent = m
		table.insert(coins, {Part = c, Ready = true, Mesh = template ~= nil})
	end
	task.spawn(function()
		local spin = 0
		while true do
			local dt = task.wait(0.2)
			spin = spin + dt * 2
			for _, pl in ipairs(Players:GetPlayers()) do
				local char, _, root = body(pl)
				if char and active(pl) then
					for _, coin in ipairs(coins) do
						if coin.Ready and (root.Position - coin.Part.Position).Magnitude < 5 and allow(pl, "coin", 0.15) then
							coin.Ready = false; coin.Part.Transparency = 1
							award(pl, Config.CoinValue); notice(pl, "+" .. Config.CoinValue, "Coin")
							task.delay(math.random(Config.CoinRespawn[1], Config.CoinRespawn[2]), function() coin.Ready = true; coin.Part.Transparency = 0 end)
						end
					end
				end
			end
			for _, coin in ipairs(coins) do
				if coin.Ready then
					coin.Part.CFrame = CFrame.new(coin.Part.Position) * (coin.Mesh and CFrame.Angles(0, spin, 0) or CFrame.Angles(0, spin, math.pi / 2))
				end
			end
		end
	end)
end

-- ---------------------------------------------------------------- boost pads (WalkSpeed replicates; the pad only changes speed)
do
	local pads = track:FindFirstChild("Boosts") and track.Boosts:GetChildren() or {}
	for _, pad in ipairs(pads) do
		pad.Touched:Connect(function(hit)
			local pl = playerFromHit(hit)
			if pl and body(pl) and allow(pl, "boost", 0.5) then
				boostUntil[pl] = os.clock() + Config.Boost.Duration
				applyStats(pl); notice(pl, "", "Boost", Config.Boost.Duration)
				task.delay(Config.Boost.Duration, function() if pl.Parent then applyStats(pl) end end)
			end
		end)
	end
end

-- ---------------------------------------------------------------- fall guard
task.spawn(function()
	while true do
		task.wait(0.2)
		for _, pl in ipairs(Players:GetPlayers()) do
			local char, _, root = body(pl)
			if char and root.Position.Y < Config.FallY then
				teleport(pl, returnPoint(pl))
				notice(pl, race.Racers[pl] and "رجعت لآخر نقطة حفظ" or "رجعت للجزيرة")
			end
		end
	end
end)

-- ---------------------------------------------------------------- players
local function joined(player)
	local p = Profiles.Load(player)
	if not p then return end
	if player.Parent ~= Players then Profiles.Save(player, true); return end
	local leader = Instance.new("Folder"); leader.Name = "leaderstats"
	local coins = Instance.new("IntValue"); coins.Name = "Coins"; coins.Value = p.Coins; coins.Parent = leader
	local wins = Instance.new("IntValue"); wins.Name = "Wins"; wins.Value = p.Wins; wins.Parent = leader
	leader.Parent = player
	local daily, streak = Rules.dailyReward(p, today(), Config)
	if daily then task.delay(4, function() notice(player, "مكافأة اليوم " .. streak .. ": +" .. daily .. " عملة 🎁", "Daily") end) end
	local function spawned(char)
		local hum = char:WaitForChild("Humanoid", 10)
		char:WaitForChild("HumanoidRootPart", 10)
		if not hum then return end
		task.wait(0.3)
		if player.Character ~= char then return end
		applyStats(player)
		if race.Racers[player] and not race.Racers[player].Finished then
			teleport(player, returnPoint(player))
			if race.Phase == "Countdown" then freeze(player, true) end
		end
		send(player)
	end
	player.CharacterAdded:Connect(spawned)
	if player.Character then task.spawn(spawned, player.Character) end
	send(player)
end
Players.PlayerAdded:Connect(joined)
for _, pl in ipairs(Players:GetPlayers()) do task.spawn(joined, pl) end
Players.PlayerRemoving:Connect(function(player)
	race.Joined[player] = nil; race.Racers[player] = nil
	cooldown[player] = nil; boostUntil[player] = nil; lastCheckpoint[player] = nil
	Profiles.Save(player, true)
	if race.Phase == "Idle" then setPhase(race.Phase, race.Deadline) end
end)
task.spawn(function()
	while task.wait(60) do
		for player, p in pairs(Profiles.Live) do
			if not p.Closing then task.spawn(function() Profiles.Save(player, false); send(player) end) end
		end
	end
end)
task.spawn(function() while task.wait(5) do Profiles.Watchdog() end end)
game:BindToClose(function()
	local pending = 0
	for player in pairs(Profiles.Live) do
		pending = pending + 1
		task.spawn(function() Profiles.Save(player, true); pending = pending - 1 end)
	end
	local untilTime = os.clock() + 25
	while pending > 0 and os.clock() < untilTime do task.wait(0.1) end
end)
print(string.format("[Island Race] server ready: track %s, %d checkpoints, %d grid slots", trackDef.Id, CP, #gridSlots))
