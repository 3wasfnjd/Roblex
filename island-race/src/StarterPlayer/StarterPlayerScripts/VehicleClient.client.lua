-- Client-side movement effects. The character is simulated on this device, so velocity
-- changes (jump pads) and the hoverboard glide must be applied here, not on the server.
local Players = game:GetService("Players")
local RS = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")
local player = Players.LocalPlayer
local shared = RS:WaitForChild("IslandRace")
local Config = require(shared:WaitForChild("Config"))
local rem = shared:WaitForChild("Remotes")
local NoticeRemote = rem:WaitForChild("Notice")
local map = workspace:WaitForChild("IslandRace")

local function body()
	local c = player.Character
	local r = c and c:FindFirstChild("HumanoidRootPart")
	local h = c and c:FindFirstChildOfClass("Humanoid")
	if c and r and h and h.Health > 0 then return c, r, h end
	return nil
end

-- ---------------------------------------------------------------- jump pads
local cool = 0
local function launch(r, h, up)
	h:ChangeState(Enum.HumanoidStateType.Jumping)
	local v = r.AssemblyLinearVelocity
	r.AssemblyLinearVelocity = Vector3.new(v.X, up, v.Z)
	task.wait()
	if r.Parent and r.AssemblyLinearVelocity.Y < up * 0.6 then
		v = r.AssemblyLinearVelocity; r.AssemblyLinearVelocity = Vector3.new(v.X, up, v.Z)
	end
end
local function hookPad(pad)
	pad.Touched:Connect(function(hit)
		local c, r, h = body()
		if not c or not hit:IsDescendantOf(c) or os.clock() < cool then return end
		cool = os.clock() + 0.6
		launch(r, h, Config.JumpPad.Velocity)
		TweenService:Create(pad, TweenInfo.new(0.12, Enum.EasingStyle.Quad, Enum.EasingDirection.Out, 0, true), {Size = pad.Size * Vector3.new(1.1, 0.5, 1.1)}):Play()
	end)
end
local function watchFolder(folder)
	for _, p in ipairs(folder:GetChildren()) do if p:IsA("BasePart") then hookPad(p) end end
	folder.ChildAdded:Connect(function(p) if p:IsA("BasePart") then hookPad(p) end end)
end
for _, d in ipairs(map:GetDescendants()) do if d:IsA("Folder") and d.Name == "JumpPads" then watchFolder(d) end end
map.DescendantAdded:Connect(function(d) if d:IsA("Folder") and d.Name == "JumpPads" then watchFolder(d) end end)

-- ---------------------------------------------------------------- hoverboard glide (reduced gravity while falling)
local force
RunService.Heartbeat:Connect(function()
	local c, r, h = body()
	if not c then return end
	local glide = c:GetAttribute("Glide") or 0
	local falling = h:GetState() == Enum.HumanoidStateType.Freefall and r.AssemblyLinearVelocity.Y < 0
	if glide > 0 and falling then
		if not force or force.Parent ~= r then
			local a = r:FindFirstChild("GlideAttachment") or Instance.new("Attachment"); a.Name = "GlideAttachment"; a.Parent = r
			force = Instance.new("VectorForce"); force.Name = "Glide"; force.Attachment0 = a; force.RelativeTo = Enum.ActuatorRelativeTo.World; force.ApplyAtCenterOfMass = true; force.Parent = r
		end
		local mass = 0
		for _, part in ipairs(c:GetDescendants()) do if part:IsA("BasePart") and not part.Massless then mass = mass + part:GetMass() end end
		force.Force = Vector3.new(0, mass * workspace.Gravity * glide, 0); force.Enabled = true
	elseif force then
		force.Enabled = false
	end
end)

-- ---------------------------------------------------------------- boost speed lines
local gui = Instance.new("ScreenGui"); gui.Name = "SpeedFX"; gui.ResetOnSpawn = false; gui.IgnoreGuiInset = true; gui.DisplayOrder = -1; gui.Parent = player:WaitForChild("PlayerGui")
local lines = {}
for i = 1, 14 do
	local f = Instance.new("Frame"); f.BorderSizePixel = 0; f.BackgroundColor3 = Color3.fromRGB(255, 220, 160); f.BackgroundTransparency = 1
	f.AnchorPoint = Vector2.new(0.5, 0.5); f.Position = UDim2.fromScale(i <= 7 and 0.06 + (i - 1) * 0.015 or 0.94 - (i - 8) * 0.015, 0.5)
	f.Size = UDim2.new(0, 3, math.random(30, 70) / 100, 0); f.Rotation = (i <= 7 and -1 or 1) * (6 + (i % 7) * 4); f.Parent = gui
	lines[i] = f
end
local boostToken = 0
NoticeRemote.OnClientEvent:Connect(function(_, kind, seconds)
	if kind ~= "Boost" then return end
	boostToken = boostToken + 1; local token = boostToken
	for _, f in ipairs(lines) do TweenService:Create(f, TweenInfo.new(0.15), {BackgroundTransparency = 0.35}):Play() end
	task.delay((tonumber(seconds) or 3) - 0.3, function()
		if boostToken ~= token then return end
		for _, f in ipairs(lines) do TweenService:Create(f, TweenInfo.new(0.4), {BackgroundTransparency = 1}):Play() end
	end)
end)
