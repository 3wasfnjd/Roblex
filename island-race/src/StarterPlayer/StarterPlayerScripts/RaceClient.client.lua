-- Island Race HUD: coins, race status, join button, results, shop, notices.
local Players = game:GetService("Players")
local RS = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")
local UserInputService = game:GetService("UserInputService")
local player = Players.LocalPlayer

local shared = RS:WaitForChild("IslandRace")
local Config = require(shared:WaitForChild("Config"))
local Rules = require(shared:WaitForChild("Rules"))
local rem = shared:WaitForChild("Remotes")
local StateRemote, ActionRemote, NoticeRemote, RaceRemote = rem:WaitForChild("State"), rem:WaitForChild("Action"), rem:WaitForChild("Notice"), rem:WaitForChild("Race")

local state = {Coins = 0, Vehicles = {run = true}, Equipped = "run", Upgrades = {}, BestTimes = {}, Race = {Phase = "Idle", Joined = {}}}
local live = nil     -- latest race tick

local C = {bg = Color3.fromRGB(22, 30, 60), panel = Color3.fromRGB(30, 40, 78), ink = Color3.new(1, 1, 1), muted = Color3.fromRGB(170, 185, 220),
	blue = Color3.fromRGB(60, 150, 255), orange = Color3.fromRGB(255, 150, 40), green = Color3.fromRGB(70, 210, 120), red = Color3.fromRGB(240, 80, 80)}
local gui = Instance.new("ScreenGui"); gui.Name = "RaceUI"; gui.ResetOnSpawn = false; gui.IgnoreGuiInset = false; gui.ZIndexBehavior = Enum.ZIndexBehavior.Sibling; gui.Parent = player:WaitForChild("PlayerGui")

local function make(class, props, parent)
	local o = Instance.new(class)
	for k, v in pairs(props) do o[k] = v end
	o.Parent = parent; return o
end
local function round(o, r) make("UICorner", {CornerRadius = UDim.new(0, r or 12)}, o) end
local function stroke(o, color, t) make("UIStroke", {Color = color or C.blue, Thickness = t or 2, ApplyStrokeMode = Enum.ApplyStrokeMode.Border}, o) end
local function label(parent, text, pos, size, fontSize, color)
	return make("TextLabel", {Text = text, Position = pos, Size = size, BackgroundTransparency = 1, TextColor3 = color or C.ink, Font = Enum.Font.GothamBold, TextSize = fontSize or 18, TextWrapped = true}, parent)
end
local function button(parent, text, pos, size, cb, color)
	local b = make("TextButton", {Text = text, Position = pos, Size = size, BackgroundColor3 = color or C.blue, BorderSizePixel = 0, TextColor3 = C.ink, TextSize = 18, Font = Enum.Font.GothamBlack, AutoButtonColor = true, TextWrapped = true}, parent)
	round(b, 12); stroke(b, Color3.new(1, 1, 1), 2)
	b.Activated:Connect(cb); return b
end

-- top bar: coins (left) and race status (center)
local coinBox = make("Frame", {Position = UDim2.new(0, 12, 0, 12), Size = UDim2.fromOffset(150, 44), BackgroundColor3 = C.bg, BackgroundTransparency = 0.1, BorderSizePixel = 0}, gui); round(coinBox, 14); stroke(coinBox, C.orange, 2)
local coinText = label(coinBox, "🪙 0", UDim2.fromOffset(0, 0), UDim2.fromScale(1, 1), 22, C.orange)
local status = make("Frame", {AnchorPoint = Vector2.new(0.5, 0), Position = UDim2.new(0.5, 0, 0, 12), Size = UDim2.fromOffset(360, 64), BackgroundColor3 = C.bg, BackgroundTransparency = 0.1, BorderSizePixel = 0}, gui); round(status, 16); stroke(status, C.blue, 2)
local statusTop = label(status, "", UDim2.fromOffset(0, 4), UDim2.new(1, 0, 0, 30), 22)
local statusSub = label(status, "", UDim2.fromOffset(0, 34), UDim2.new(1, 0, 0, 24), 15, C.muted)

-- right side: shop/menu button
local menuBtn = button(gui, "🏎 المتجر", UDim2.new(1, -12, 0, 12), UDim2.fromOffset(120, 44), function() end, C.panel)
menuBtn.AnchorPoint = Vector2.new(1, 0)

-- bottom: join button
local joinBtn = button(gui, "انضم للسباق 🏁", UDim2.new(0.5, 0, 1, -24), UDim2.fromOffset(260, 56), function() ActionRemote:FireServer("join") end, C.green)
joinBtn.AnchorPoint = Vector2.new(0.5, 1); joinBtn.TextSize = 22

-- toast
local toast = label(gui, "", UDim2.new(0.5, -200, 0.72, 0), UDim2.fromOffset(400, 56), 19); toast.AnchorPoint = Vector2.new(0, 0)
toast.BackgroundColor3 = C.bg; toast.BackgroundTransparency = 0.08; toast.Visible = false; round(toast, 16); stroke(toast, C.orange, 2)
local toastToken = 0
local function notify(text, color)
	if not text or text == "" then return end
	toastToken = toastToken + 1; local token = toastToken
	toast.Text = text; toast.TextColor3 = color or C.ink; toast.Visible = true
	task.delay(3.5, function() if toastToken == token then toast.Visible = false end end)
end

-- big center flash (countdown numbers, GO, lap)
local flash = label(gui, "", UDim2.fromScale(0.5, 0.3), UDim2.fromOffset(600, 120), 96, C.orange); flash.AnchorPoint = Vector2.new(0.5, 0.5); flash.Font = Enum.Font.GothamBlack
make("UIStroke", {Color = C.bg, Thickness = 4}, flash)
local flashToken = 0
local function showFlash(text, color, seconds)
	flashToken = flashToken + 1; local token = flashToken
	flash.Text = text; flash.TextColor3 = color or C.orange; flash.TextTransparency = 0; flash.Visible = true
	task.delay(seconds or 0.9, function() if flashToken == token then flash.Visible = false end end)
end

-- live race board (right side during a race)
local board = make("Frame", {AnchorPoint = Vector2.new(1, 0), Position = UDim2.new(1, -12, 0, 66), Size = UDim2.fromOffset(220, 0), AutomaticSize = Enum.AutomaticSize.Y, BackgroundColor3 = C.bg, BackgroundTransparency = 0.15, BorderSizePixel = 0, Visible = false}, gui); round(board, 14)
make("UIListLayout", {Padding = UDim.new(0, 4), SortOrder = Enum.SortOrder.LayoutOrder}, board)
make("UIPadding", {PaddingTop = UDim.new(0, 8), PaddingBottom = UDim.new(0, 8), PaddingLeft = UDim.new(0, 10), PaddingRight = UDim.new(0, 10)}, board)
local boardRows = {}
for i = 1, 8 do
	local row = label(board, "", UDim2.new(), UDim2.new(1, 0, 0, 22), 16); row.LayoutOrder = i; row.TextXAlignment = Enum.TextXAlignment.Right; boardRows[i] = row
end

-- overlay panel (shop + results)
local overlay = make("Frame", {Size = UDim2.fromScale(1, 1), BackgroundColor3 = Color3.new(0, 0, 0), BackgroundTransparency = 0.5, Visible = false}, gui)
local panel = make("Frame", {AnchorPoint = Vector2.new(0.5, 0.5), Position = UDim2.fromScale(0.5, 0.5), Size = UDim2.fromOffset(640, 480), BackgroundColor3 = C.bg, BorderSizePixel = 0}, overlay); round(panel, 22); stroke(panel, C.blue, 3)
local title = label(panel, "", UDim2.fromOffset(60, 14), UDim2.new(1, -120, 0, 40), 26, C.orange)
button(panel, "×", UDim2.fromOffset(14, 14), UDim2.fromOffset(40, 40), function() overlay.Visible = false end, C.red)
local content = make("ScrollingFrame", {Position = UDim2.fromOffset(16, 66), Size = UDim2.new(1, -32, 1, -82), BackgroundTransparency = 1, BorderSizePixel = 0, ScrollBarThickness = 6, ScrollBarImageColor3 = C.blue, CanvasSize = UDim2.new(), AutomaticCanvasSize = Enum.AutomaticSize.Y, ScrollingDirection = Enum.ScrollingDirection.Y}, panel)
local page = nil
local function open(t, kind)
	title.Text = t; page = kind; overlay.Visible = true
	for _, c in ipairs(content:GetChildren()) do c:Destroy() end
	content.CanvasPosition = Vector2.zero
end

local function drawShop()
	open("🏎 كراج المركبات", "Shop")
	local y = 0
	for _, v in ipairs(Config.Vehicles) do
		local owned = state.Vehicles[v.Id]; local equipped = state.Equipped == v.Id
		local card = make("Frame", {Position = UDim2.fromOffset(0, y), Size = UDim2.new(1, -8, 0, 150), BackgroundColor3 = C.panel, BorderSizePixel = 0}, content); round(card, 16); stroke(card, equipped and C.green or C.panel, 2)
		local l = label(card, v.Name, UDim2.fromOffset(12, 10), UDim2.new(1, -24, 0, 28), 22); l.TextXAlignment = Enum.TextXAlignment.Right
		local d = label(card, v.Desc .. "  •  سرعة " .. v.WalkSpeed .. "  •  قفزة " .. v.JumpPower, UDim2.fromOffset(12, 40), UDim2.new(1, -24, 0, 24), 14, C.muted); d.TextXAlignment = Enum.TextXAlignment.Right
		if owned then
			button(card, equipped and "مجهّزة ✓" or "تجهيز", UDim2.fromOffset(12, 72), UDim2.fromOffset(150, 40), function() if not equipped then ActionRemote:FireServer("equip", v.Id) end end, equipped and C.green or C.blue)
			-- upgrades
			local x = 180
			for _, u in ipairs(Config.Upgrades) do
				local lvl = state.Upgrades[v.Id] and state.Upgrades[v.Id][u.Key] or 0
				local maxed = lvl >= #u.Prices
				local txt = u.Name .. " " .. lvl .. "/" .. #u.Prices .. (maxed and "" or ("  🪙 " .. u.Prices[lvl + 1]))
				button(card, txt, UDim2.fromOffset(x, 72), UDim2.fromOffset(210, 40), function() if not maxed then ActionRemote:FireServer("upgrade", v.Id, u.Key) end end, maxed and C.panel or C.orange)
				x = x + 220
			end
		else
			button(card, "شراء 🪙 " .. v.Price, UDim2.fromOffset(12, 72), UDim2.fromOffset(170, 40), function() ActionRemote:FireServer("buy", v.Id) end, state.Coins >= v.Price and C.orange or C.panel)
		end
		y = y + 160
	end
	local best = state.BestTimes[Config.Tracks[1].Id]
	label(content, "أفضل زمن لك على " .. Config.Tracks[1].Name .. ": " .. Rules.formatTime(best) .. "   •   فوز: " .. (state.Wins or 0) .. "   •   سباقات: " .. (state.Races or 0), UDim2.fromOffset(0, y + 4), UDim2.new(1, -8, 0, 30), 15, C.muted)
end
menuBtn.Activated:Connect(function() if overlay.Visible and page == "Shop" then overlay.Visible = false else drawShop() end end)

local function drawResults(data)
	open("🏁 نتائج السباق • " .. (data.Track or ""), "Results")
	local y = 0
	for _, r in ipairs(data.List) do
		local me = r.UserId == player.UserId
		local row = make("Frame", {Position = UDim2.fromOffset(0, y), Size = UDim2.new(1, -8, 0, 44), BackgroundColor3 = me and C.panel or C.bg, BorderSizePixel = 0}, content); round(row, 10)
		local medal = r.Finished and (({"🥇", "🥈", "🥉"})[r.Place] or tostring(r.Place)) or "✗"
		local t = label(row, medal .. "  " .. r.Name .. "   " .. (r.Finished and Rules.formatTime(r.Time) or "لم يكمل") .. "   +" .. r.Reward .. " 🪙" .. (r.NewBest and "  ⭐ رقم جديد" or ""), UDim2.fromOffset(10, 0), UDim2.new(1, -20, 1, 0), 17, me and C.orange or C.ink)
		t.TextXAlignment = Enum.TextXAlignment.Right
		y = y + 50
	end
	if #data.List == 0 then label(content, "لم يشارك أحد", UDim2.fromOffset(0, 10), UDim2.new(1, 0, 0, 40), 18, C.muted) end
end

-- remotes
StateRemote.OnClientEvent:Connect(function(s)
	state = s; coinText.Text = "🪙 " .. tostring(s.Coins)
	if overlay.Visible and page == "Shop" then local pos = content.CanvasPosition; drawShop(); content.CanvasPosition = pos end
end)
NoticeRemote.OnClientEvent:Connect(function(text, kind, data)
	if kind == "Shop" then drawShop()
	elseif kind == "Go" then showFlash("انطلق!", C.green, 1.2); notify(text)
	elseif kind == "Lap" then showFlash(text, C.blue, 1.2)
	elseif kind == "Finish" then showFlash("وصلت! 🏁", C.orange, 1.5); notify(text)
	elseif kind == "Win" then
		notify(text, C.orange)
		for i = 1, 36 do
			local dot = make("Frame", {Position = UDim2.fromScale(math.random(), -0.04), Size = UDim2.fromOffset(8, 14), BackgroundColor3 = Color3.fromHSV(i / 36, 0.7, 1), BorderSizePixel = 0, Rotation = math.random(180)}, gui)
			TweenService:Create(dot, TweenInfo.new(2 + math.random()), {Position = UDim2.fromScale(math.random(), 1.1), Rotation = math.random(600)}):Play()
			task.delay(3.3, function() dot:Destroy() end)
		end
	elseif kind == "Coin" then
		notify(text, C.orange)
	elseif kind == "Boost" then
		-- speed lines handled by VehicleClient
	else notify(text) end
end)
RaceRemote.OnClientEvent:Connect(function(kind, data)
	if kind == "phase" then
		state.Race = data; live = nil
		if data.Phase == "Countdown" then
			task.spawn(function()
				for n = Config.Race.Countdown, 1, -1 do
					if state.Race.Phase ~= "Countdown" then return end
					showFlash(tostring(n), n <= 2 and C.red or C.orange, 0.9); task.wait(1)
				end
			end)
		end
		if data.Phase ~= "Results" and overlay.Visible and page == "Results" then overlay.Visible = false end
	elseif kind == "tick" then live = data
	elseif kind == "results" then drawResults(data) end
end)

-- HUD refresh
local function iAmJoined()
	for _, id in ipairs(state.Race.Joined or {}) do if id == player.UserId then return true end end
	return false
end
local timer = 0
RunService.RenderStepped:Connect(function(dt)
	timer = timer + dt; if timer < 0.1 then return end; timer = 0
	local r = state.Race or {}
	local left = math.max(0, math.ceil((r.Deadline or 0) - workspace:GetServerTimeNow()))
	local joined = iAmJoined()
	joinBtn.Visible = r.Phase == "Idle"
	joinBtn.Text = joined and "إلغاء التسجيل" or "انضم للسباق 🏁"; joinBtn.BackgroundColor3 = joined and C.red or C.green
	board.Visible = r.Phase == "Racing" and live ~= nil
	if r.Phase == "Idle" then
		local n = #(r.Joined or {})
		statusTop.Text = n > 0 and ("السباق يبدأ خلال " .. left .. " ث") or (r.Track or "")
		statusSub.Text = n > 0 and (n .. " مسجّل • " .. (r.Laps or 2) .. " لفات") or "اضغط انضم للسباق أو بوابة السباق"
	elseif r.Phase == "Countdown" then
		statusTop.Text = "استعد… " .. left; statusSub.Text = (r.Track or "") .. " • " .. (r.Laps or 2) .. " لفات"
	elseif r.Phase == "Racing" then
		local me
		if live then for _, e in ipairs(live.Order) do if e.UserId == player.UserId then me = e end end end
		if me then
			statusTop.Text = (me.Finished and ("وصلت • " .. Rules.formatTime(me.Time))) or ("المركز " .. me.Place .. " من " .. #live.Order .. "  •  اللفة " .. me.Lap .. "/" .. live.Laps)
			statusSub.Text = "⏱ " .. Rules.formatTime(live.Elapsed)
		else
			statusTop.Text = "السباق جارٍ"; statusSub.Text = live and ("⏱ " .. Rules.formatTime(live.Elapsed)) or ""
		end
		if live then
			for i, row in ipairs(boardRows) do
				local e = live.Order[i]
				row.Text = e and ((e.Finished and "🏁 " or (i .. ". ")) .. e.Name .. (e.Finished and ("  " .. Rules.formatTime(e.Time)) or ("  لفة " .. e.Lap))) or ""
				row.TextColor3 = e and e.UserId == player.UserId and C.orange or C.ink
			end
		end
	elseif r.Phase == "Results" then
		statusTop.Text = "انتهى السباق"; statusSub.Text = "الجولة القادمة بعد " .. left .. " ث"
	end
end)
UserInputService.InputBegan:Connect(function(input, processed)
	if not processed and input.KeyCode == Enum.KeyCode.Escape then overlay.Visible = false end
end)
-- scale for phones
local function resize()
	local cam = workspace.CurrentCamera; if not cam then return end
	local v = cam.ViewportSize
	panel.Size = UDim2.fromOffset(math.min(640, v.X - 20), math.min(480, v.Y - 60))
	status.Size = UDim2.fromOffset(math.min(360, v.X - 300), 64)
end
resize()
if workspace.CurrentCamera then workspace.CurrentCamera:GetPropertyChangedSignal("ViewportSize"):Connect(resize) end
task.spawn(function()
	for _ = 1, 10 do ActionRemote:FireServer("sync"); task.wait(1); if state.Race and state.Race.Round then break end end
end)
