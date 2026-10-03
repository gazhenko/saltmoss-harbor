using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

namespace Saltmoss.EditorTools
{
    /// <summary>
    /// Generates the Saltmoss scene from Data/town_layout.json (written by the set builder in Tools/clay): terrain
    /// tiles, every building and prop with colliders, the cast at their posts, Pip, the Sally Mae at her berth, the
    /// fishing systems, lamps, scattered sea set-pieces and cotton clouds, title camera shots, and a baked shore-foam
    /// map so white clay foam rings every piling and rock.
    /// </summary>
    public static class WorldBuilder
    {
        const string LayoutPath = "Assets/Saltmoss/Data/town_layout.json";

        [Serializable] class Inst { public string model; public float[] pos; public float yaw; public float scale = 1f; public string collide; public string tag; }
        [Serializable] class Terrain { public string[] tiles; public float tile_size = 40f; public float[] origin; }
        [Serializable] class Layout { public Inst[] instances; public Terrain terrain; }

        static Dictionary<string, object> anchors;

        [MenuItem("Saltmoss/Scenes/Build World")]
        public static void Build()
        {
            var json = File.ReadAllText(LayoutPath);
            var layout = JsonUtility.FromJson<Layout>(json);
            anchors = MiniJson.Parse(json) is Dictionary<string, object> root && root.TryGetValue("anchors", out var a) ? a as Dictionary<string, object> : new Dictionary<string, object>();

            var scene = SceneKit.NewScene("Saltmoss");
            var dc = SceneKit.Lighting(9f);
            SceneKit.PostVolume();
            SceneKit.Backdrop();
            var sea = SceneKit.Sea();
            var mouth = Pos("harbor_mouth", new Vector3(0, 0, 75));
            sea.roughCentre = new Vector2(mouth.x, mouth.z);

            var world = new GameObject("World").transform;
            // ---------------------------------------------------------------- terrain
            var terr = new GameObject("Terrain").transform;
            terr.SetParent(world);
            if (layout.terrain != null && layout.terrain.tiles != null)
                foreach (var t in layout.terrain.tiles)
                {
                    // tiles are authored in world coordinates
                    var go = SceneKit.Place("terrain/" + t, Vector3.zero, 0f, terr);
                    if (go == null) continue;
                    Collide(go, "mesh");
                    Static(go);
                }

            // ---------------------------------------------------------------- town
            var town = new GameObject("Town").transform;
            town.SetParent(world);
            var restoration = new GameObject("Restoration").AddComponent<Restoration>();
            GameObject shopGo = null, museumGo = null, lighthouseGo = null, boardGo = null;
            foreach (var inst in layout.instances)
            {
                var go = SceneKit.Place(inst.model, V(inst.pos), inst.yaw, town, inst.scale <= 0 ? 1f : inst.scale);
                if (go == null) continue;
                Collide(go, inst.collide);
                string tag = inst.tag ?? "";
                if (tag == "shop" && shopGo == null) shopGo = go;
                if (tag == "museum") museumGo = go;
                if (tag == "lighthouse") lighthouseGo = go;
                if (tag == "office") boardGo = go;
                if (tag.Contains("tier1")) restoration.tier1.Add(go);
                if (tag.Contains("tier2")) restoration.tier2.Add(go);
                if (tag.Contains("tier3")) restoration.tier3.Add(go);
                if (tag.Contains("shabby")) restoration.shabby.Add(go);
                if (!tag.Contains("tier") && !tag.Contains("shabby")) Static(go);
            }

            // ---------------------------------------------------------------- painted signs
            var ui = AssetDatabase.LoadAssetAtPath<UIBank>($"{BankBuilder.ResDir}/UIBank.asset");
            foreach (var m in town.GetComponentsInChildren<ClayModel>(true))
            {
                var sign = m.Socket("sign_text");
                if (sign != null)
                    Sign(sign, m.name.Contains("fish_shop") ? "The Salty Puffin" : m.name.Contains("post") ? "Post Office" : m.name.Contains("museum") ? "Tidewrack Museum" : "",
                        ui != null ? ui.display : null, new Color(0.97f, 0.93f, 0.82f), 1.6f);
                var board = m.Socket("board_text");
                if (board != null)
                {
                    var t = Sign(board, "FORECAST", ui != null ? ui.body : null, new Color(0.93f, 0.93f, 0.9f), 0.9f);
                    t.alignment = TMPro.TextAlignmentOptions.Top;
                    t.rectTransform.sizeDelta = new Vector2(1.6f, 1.2f);
                    board.gameObject.AddComponent<ForecastBoard>().text = t;
                }
            }

            // ---------------------------------------------------------------- lamps
            var lamps = new GameObject("Lamps").transform;
            lamps.SetParent(world);
            foreach (var p in PosList("lantern_lights"))
            {
                var l = Lamp(lamps, p, new Color(1f, 0.72f, 0.42f), 7f);
                restoration.lanternLights.Add(l);
            }
            foreach (var p in PosList("window_lights")) restoration.lanternLights.Add(Lamp(lamps, p, new Color(1f, 0.78f, 0.5f), 5f));
            if (lighthouseGo != null)
            {
                var sock = Socket(lighthouseGo, "lamp");
                var lgo = new GameObject("LighthouseBeam");
                lgo.transform.position = sock != null ? sock.position : lighthouseGo.transform.position + Vector3.up * 12f;
                var l = lgo.AddComponent<Light>();
                l.type = LightType.Spot;
                l.spotAngle = 26f;
                l.range = 220f;
                l.color = new Color(1f, 0.92f, 0.7f);
                l.renderingLayerMask = 1;
                restoration.lighthouse = l;
            }

            // ---------------------------------------------------------------- systems
            var sys = new GameObject("Systems");
            sys.AddComponent<GameFlow>();
            sys.AddComponent<Story>();
            var pots = sys.AddComponent<CrabPots>();
            sys.AddComponent<RodFishing>();
            var dredge = sys.AddComponent<Dredge>();
            sys.AddComponent<SeaHazards>();
            sys.AddComponent<SeaActions>();
            sys.AddComponent<PotsVisual>();
            sys.AddComponent<Weather3D>();
            sys.AddComponent<AmbientLife>();
            var refs = sys.AddComponent<WorldRefs>();
            var boot = sys.AddComponent<GameBoot>();
            refs.playerSpawn = Anchor("player_spawn", world);
            refs.pipDoor = Anchor("pip_door", world);
            refs.shopStand = Anchor("shop_counter", world);
            refs.museumDoor = Anchor("museum_door", world);
            refs.board = Anchor("board", world);

            // ---------------------------------------------------------------- shop
            var counter = new GameObject("ShopCounter");
            counter.transform.position = refs.shopStand != null ? refs.shopStand.position : Vector3.zero;
            var shop = counter.AddComponent<ShopCounter>();
            shop.standPoint = refs.shopStand;
            shop.radius = 2.2f;
            shop.queue = PosList("queue").ToArray();
            var path = PosList("customer_path");
            if (path.Count == 0) path.Add(Pos("customer_spawn", Vector3.zero));
            shop.path = path.ToArray();
            if (shopGo != null)
            {
                var slots = new List<Transform>();
                for (int i = 0; i < 12; i++) { var s = Socket(shopGo, "display_" + i); if (s != null) slots.Add(s); }
                shop.displaySlots = slots.ToArray();
            }

            // ---------------------------------------------------------------- museum
            if (museumGo != null)
            {
                var m = museumGo.AddComponent<Museum>();
                var ts = new List<Transform>();
                var fs = new List<Transform>();
                for (int i = 0; i < 24; i++) { var s = Socket(museumGo, "slot_" + i); if (s != null) ts.Add(s); }
                for (int i = 0; i < 24; i++) { var s = Socket(museumGo, "tank_" + i); if (s != null) fs.Add(s); }
                m.treasureSlots = ts.ToArray();
                m.fishSlots = fs.ToArray();
            }
            else new GameObject("Museum").AddComponent<Museum>();

            // ---------------------------------------------------------------- interactables
            if (refs.board != null)
            {
                var b = refs.board.gameObject.AddComponent<SimpleInteractNode>();
                b.prompt = "Read the forecast board";
                b.node = "forecast_board";
                b.partner = "walter";
                b.radius = 2.2f;
            }
            if (refs.pipDoor != null)
            {
                var d = refs.pipDoor.gameObject.AddComponent<SimpleInteractNode>();
                d.prompt = "Pip's front door";
                d.node = "pip_door";
                d.radius = 1.8f;
            }

            // ---------------------------------------------------------------- cast
            var cast = new GameObject("Cast").transform;
            var player = MakeCritter("pip", refs.playerSpawn != null ? refs.playerSpawn.position : Vector3.zero, refs.playerSpawn != null ? refs.playerSpawn.eulerAngles.y : 0f, cast, true);
            boot.player = player.GetComponent<PlayerController>();
            MakeNpc("walter", "walter_post", cast);
            MakeNpc("nell", "nell_post", cast);
            MakeNpc("marge", "marge_post", cast);
            MakeNpc("inkwell", "inkwell_post", cast);
            var shelby = MakeNpc("shelby", "shelby_post", cast);
            if (shelby != null && anchors.TryGetValue("shelby_wander", out var sw) && sw is Dictionary<string, object> swd)
                shelby.GetComponent<Npc>().wanderRadius = Convert.ToSingle(swd["radius"]);

            // ---------------------------------------------------------------- the Sally Mae
            boot.boat = MakeBoat(cast, mouth);
            dredge.wreck = new Vector3(-140f, 0f, mouth.z + 470f);

            // ---------------------------------------------------------------- sea set pieces & sky
            Scatter(world, mouth, dredge.wreck);

            // ---------------------------------------------------------------- camera
            var cam = SceneKit.MainCamera(refs.playerSpawn != null ? refs.playerSpawn.position + new Vector3(0, 3, -7) : new Vector3(0, 4, -10), refs.playerSpawn != null ? refs.playerSpawn.position : Vector3.zero);
            var rig = cam.gameObject.AddComponent<CameraRig>();
            rig.target = player.transform;
            rig.obstacles = 1 << ProjectSetup.LayerWorld;
            cam.GetComponent<ClayLens>().focusTarget = player.transform;
            refs.titleShots = TitleShots(world, mouth);

            // ---------------------------------------------------------------- shore foam
            Physics.SyncTransforms();
            BakeShoreFoam(sea);

            SceneKit.Save(scene);
        }

        // ================================================================ helpers

        static Vector3 V(float[] p) => p == null || p.Length < 3 ? Vector3.zero : new Vector3(p[0], p[1], p[2]);

        static Vector3 Pos(string key, Vector3 fallback)
        {
            if (anchors != null && anchors.TryGetValue(key, out var o) && o is Dictionary<string, object> d && d.TryGetValue("pos", out var p))
                return ToV(p);
            return fallback;
        }

        static float Yaw(string key)
        {
            if (anchors != null && anchors.TryGetValue(key, out var o) && o is Dictionary<string, object> d && d.TryGetValue("yaw", out var y))
                return Convert.ToSingle(y);
            return 0f;
        }

        static Vector3 ToV(object p)
        {
            var l = p as List<object>;
            return l == null || l.Count < 3 ? Vector3.zero : new Vector3(Convert.ToSingle(l[0]), Convert.ToSingle(l[1]), Convert.ToSingle(l[2]));
        }

        static List<Vector3> PosList(string key)
        {
            var r = new List<Vector3>();
            if (anchors != null && anchors.TryGetValue(key, out var o) && o is List<object> l)
                foreach (var p in l) r.Add(ToV(p));
            return r;
        }

        static Transform Anchor(string key, Transform parent)
        {
            if (anchors == null || !anchors.ContainsKey(key)) return null;
            var t = new GameObject("anchor_" + key).transform;
            t.SetParent(parent);
            t.SetPositionAndRotation(Pos(key, Vector3.zero), Quaternion.Euler(0, Yaw(key), 0));
            return t;
        }

        static Transform Socket(GameObject go, string name)
        {
            var m = go.GetComponent<ClayModel>();
            return m != null ? m.Socket(name) : null;
        }

        static void Static(GameObject go)
        {
            foreach (var t in go.GetComponentsInChildren<Transform>(true))
                GameObjectUtility.SetStaticEditorFlags(t.gameObject, StaticEditorFlags.BatchingStatic | StaticEditorFlags.OccluderStatic | StaticEditorFlags.OccludeeStatic);
        }

        static void Collide(GameObject go, string mode)
        {
            foreach (var t in go.GetComponentsInChildren<Transform>(true)) t.gameObject.layer = ProjectSetup.LayerWorld;
            if (string.IsNullOrEmpty(mode) || mode == "none") return;
            if (mode == "box")
            {
                var b = go.GetComponent<ClayModel>().VisualBounds();
                var bc = go.AddComponent<BoxCollider>();
                bc.center = go.transform.InverseTransformPoint(b.center);
                var s = go.transform.lossyScale;
                bc.size = new Vector3(b.size.x / s.x, b.size.y / s.y, b.size.z / s.z);
                return;
            }
            foreach (var mf in go.GetComponentsInChildren<MeshFilter>(true))
            {
                var mr = mf.GetComponent<MeshRenderer>();
                if (mr == null || !mf.gameObject.activeSelf) continue;
                if (mr.sharedMaterial != null && (mr.sharedMaterial.name == "ClayGlow" || mr.sharedMaterial.name == "Cotton")) continue;
                var mc = mf.gameObject.AddComponent<MeshCollider>();
                mc.sharedMesh = mf.sharedMesh;
            }
        }

        static TMPro.TextMeshPro Sign(Transform socket, string text, TMPro.TMP_FontAsset font, Color color, float size)
        {
            var go = new GameObject("SignText");
            go.transform.SetParent(socket, false);
            go.transform.localPosition = new Vector3(0f, 0f, 0.02f);
            go.transform.localRotation = Quaternion.Euler(0f, 180f, 0f);
            var t = go.AddComponent<TMPro.TextMeshPro>();
            if (font != null) t.font = font;
            t.text = text;
            t.fontSize = size;
            t.color = color;
            t.alignment = TMPro.TextAlignmentOptions.Center;
            t.textWrappingMode = TMPro.TextWrappingModes.NoWrap;
            t.enableAutoSizing = true;
            t.fontSizeMax = size;
            t.fontSizeMin = size * 0.3f;
            t.rectTransform.sizeDelta = new Vector2(2.6f, 0.6f);
            return t;
        }

        static Light Lamp(Transform parent, Vector3 p, Color c, float range)
        {
            var go = new GameObject("Lamp");
            go.transform.SetParent(parent);
            go.transform.position = p;
            var l = go.AddComponent<Light>();
            l.type = LightType.Point;
            l.color = c;
            l.range = range;
            l.intensity = 0f;
            l.shadows = LightShadows.None;
            l.renderingLayerMask = 1;
            return l;
        }

        static GameObject MakeCritter(string id, Vector3 pos, float yaw, Transform parent, bool player)
        {
            var member = Cast.Get(id);
            var root = new GameObject(member.name);
            root.transform.SetParent(parent);
            root.transform.SetPositionAndRotation(pos, Quaternion.Euler(0, yaw, 0));
            root.layer = player ? ProjectSetup.LayerPlayer : ProjectSetup.LayerNPC;
            var vis = new GameObject("Visual");
            vis.transform.SetParent(root.transform, false);
            vis.AddComponent<ClayPuppet>();
            var model = SceneKit.Place(member.model, pos, yaw, vis.transform);
            if (model == null)
            {
                model = GameObject.CreatePrimitive(PrimitiveType.Capsule);
                UnityEngine.Object.DestroyImmediate(model.GetComponent<Collider>());
                model.transform.SetParent(vis.transform, false);
                model.transform.localPosition = Vector3.up;
                model.AddComponent<ClayModel>();
            }
            var cm = model.GetComponent<ClayModel>();
            var anim = model.AddComponent<CritterAnimator>();
            anim.model = cm;
            anim.personality = member.personality;
            var face = model.AddComponent<FaceRig>();
            face.model = cm;
            if (player)
            {
                var cc = root.AddComponent<CharacterController>();
                float h = Mathf.Max(0.8f, cm.VisualBounds().size.y * 0.95f);
                cc.height = h;
                cc.radius = 0.24f;
                cc.center = new Vector3(0, h * 0.5f + 0.02f, 0);
                cc.stepOffset = 0.32f;
                cc.slopeLimit = 42f;
                cc.skinWidth = 0.03f;
                var pc = root.AddComponent<PlayerController>();
                pc.anim = anim;
                pc.face = face;
                pc.model = cm;
                pc.visual = vis.transform;
            }
            return root;
        }

        static GameObject MakeNpc(string id, string post, Transform parent)
        {
            if (anchors == null || !anchors.ContainsKey(post)) return null;
            var root = MakeCritter(id, Pos(post, Vector3.zero), Yaw(post), parent, false);
            var npc = root.AddComponent<Npc>();
            npc.id = id;
            npc.anim = root.GetComponentInChildren<CritterAnimator>();
            npc.face = root.GetComponentInChildren<FaceRig>();
            npc.visual = root.transform.Find("Visual");
            npc.radius = id == "walter" || id == "marge" ? 2.4f : 2.0f;
            var col = root.AddComponent<CapsuleCollider>();
            float h = root.GetComponentInChildren<ClayModel>().VisualBounds().size.y;
            col.height = h;
            col.radius = 0.32f;
            col.center = new Vector3(0, h * 0.5f, 0);
            return root;
        }

        static BoatController MakeBoat(Transform parent, Vector3 mouth)
        {
            var berth = Pos("boat_berth", new Vector3(9, 0, 25));
            float berthYaw = Yaw("boat_berth");
            var root = new GameObject("Sally Mae");
            root.transform.SetParent(parent);
            root.transform.SetPositionAndRotation(berth, Quaternion.Euler(0, berthYaw, 0));
            root.layer = ProjectSetup.LayerBoat;
            var vis = new GameObject("Visual");
            vis.transform.SetParent(root.transform, false);
            var puppet = vis.AddComponent<ClayPuppet>();
            var model = SceneKit.Place("boat/sally_mae", berth, berthYaw, vis.transform);
            var boat = root.AddComponent<BoatController>();
            boat.puppet = puppet;
            boat.berthPos = berth;
            boat.berthYaw = berthYaw;
            boat.boardPoint = Pos("boat_board_point", berth + Vector3.left * 2.5f);
            boat.boardYaw = Yaw("boat_board_point");
            boat.harbourMouth = new Vector2(mouth.x, mouth.z);
            if (model != null)
            {
                foreach (var t in model.GetComponentsInChildren<Transform>(true)) t.gameObject.layer = ProjectSetup.LayerBoat;
                var cm = model.GetComponent<ClayModel>();
                boat.model = cm;
                boat.helm = Socket(model, "helm");
                boat.rail = Socket(model, "rail_cast");
                boat.winch = Socket(model, "winch");
                boat.boomTip = Socket(model, "boom_tip");
                boat.smoke = Socket(model, "smoke");
                boat.stern = Socket(model, "stern");
                boat.bow = Socket(model, "bow");
                var slots = new List<Transform>();
                for (int i = 0; i < 6; i++) { var s = Socket(model, "pot_slot_" + i); if (s != null) slots.Add(s); }
                boat.potSlots = slots.ToArray();
                // deck to stand on while docked (boarding is an interaction, but don't let Pip fall through)
                foreach (var mf in model.GetComponentsInChildren<MeshFilter>(true))
                    if (mf.name == "hull" || mf.name == "deck") mf.gameObject.AddComponent<MeshCollider>().sharedMesh = mf.sharedMesh;
                var name = Socket(model, "name_plate");
                if (name != null)
                {
                    var tgo = new GameObject("Name");
                    tgo.transform.SetParent(name, false);
                    var tmp = tgo.AddComponent<TMPro.TextMeshPro>();
                    tmp.text = "SALLY MAE";
                    tmp.fontSize = 3.2f;
                    tmp.alignment = TMPro.TextAlignmentOptions.Center;
                    tmp.color = new Color(0.96f, 0.92f, 0.82f);
                    var ui = AssetDatabase.LoadAssetAtPath<UIBank>($"{BankBuilder.ResDir}/UIBank.asset");
                    if (ui != null && ui.display != null) tmp.font = ui.display;
                    tgo.transform.localRotation = Quaternion.Euler(0, 180f, 0);
                }
            }
            var board = new GameObject("BoardPoint");
            board.transform.SetParent(root.transform.parent);
            board.transform.position = boat.boardPoint;
            var bi = board.AddComponent<BoardBoat>();
            bi.radius = 2.6f;
            return boat;
        }

        static void Scatter(Transform world, Vector3 mouth, Vector3 wreck)
        {
            var set = new GameObject("SeaSet").transform;
            set.SetParent(world);
            var rng = new System.Random(42);
            float R(float a, float b) => a + (float)rng.NextDouble() * (b - a);
            Vector3 Ring(float r0, float r1)
            {
                float a = R(-80f, 80f) * Mathf.Deg2Rad;
                float r = R(r0, r1);
                return new Vector3(mouth.x + Mathf.Sin(a) * r, 0f, mouth.z + Mathf.Cos(a) * r);
            }
            void Put(string id, Vector3 p, float scale = 1f, bool collide = true, float sink = 0f)
            {
                p.y -= sink;
                var go = SceneKit.Place(id, p, R(0, 360), set, scale);
                if (go == null) return;
                if (collide) Collide(go, "mesh");
                Static(go);
            }
            for (int i = 0; i < 5; i++) Put("town/sea_stack_" + (i % 2 == 0 ? "a" : "b"), Ring(120f, 420f), R(0.8f, 1.3f), true, 1.8f);
            for (int i = 0; i < 14; i++) Put("town/kelp_cluster_" + (i % 2 == 0 ? "a" : "b"), Ring(170f, 370f), R(0.9f, 1.4f), false);
            for (int i = 0; i < 9; i++) Put("town/iceberg_" + "abc"[i % 3], Ring(420f, 740f), R(0.9f, 2.2f), true, 1.2f);
            for (int i = 0; i < 4; i++) Put("town/channel_marker", new Vector3(mouth.x + (i % 2 == 0 ? -14f : 14f), 0f, mouth.z + 10f + i / 2 * 40f), 1f);
            Put("town/wreck", wreck, 1.2f, true, 0.6f);
            // cotton clouds hanging over the sea and the hills
            var sky = new GameObject("Clouds").transform;
            sky.SetParent(world);
            for (int i = 0; i < 26; i++)
            {
                float a = R(0, 360) * Mathf.Deg2Rad, r = R(160f, 900f);
                var p = new Vector3(Mathf.Sin(a) * r, R(55f, 120f), mouth.z + Mathf.Cos(a) * r);
                var go = SceneKit.Place("town/cloud_" + (1 + i % 4), p, R(0, 360), sky, R(1.2f, 3.2f));
                if (go != null) foreach (var mr in go.GetComponentsInChildren<MeshRenderer>()) mr.shadowCastingMode = ShadowCastingMode.Off;
            }
        }

        static Transform[] TitleShots(Transform world, Vector3 mouth)
        {
            var shop = Pos("shop_counter", Vector3.zero);
            var pip = Pos("pip_door", new Vector3(20, 2, 8));
            var spots = new[]
            {
                (new Vector3(-18f, 9f, 40f), shop + new Vector3(0f, 2f, 0f)),
                (new Vector3(18f, 7f, 42f), shop + new Vector3(4f, 2f, -4f)),
                (new Vector3(34f, 6f, 20f), pip + new Vector3(-6f, 1f, -4f)),
                (new Vector3(10f, 12f, 60f), new Vector3(0f, 3f, -10f)),
            };
            var list = new List<Transform>();
            var root = new GameObject("TitleShots").transform;
            root.SetParent(world);
            foreach (var (p, look) in spots)
            {
                var t = new GameObject("shot").transform;
                t.SetParent(root);
                t.SetPositionAndRotation(p, Quaternion.LookRotation(look - p));
                list.Add(t);
            }
            return list.ToArray();
        }

        /// <summary>Probe the waterline on a grid: wherever something stands in the water, ring it with foam.</summary>
        static void BakeShoreFoam(SeaState sea)
        {
            const int N = 1024;
            const float size = 320f;
            var origin = new Vector2(-160f, -130f);
            float cell = size / N;
            var solid = new float[N, N];
            int mask = 1 << ProjectSetup.LayerWorld;
            for (int j = 0; j < N; j++)
                for (int i = 0; i < N; i++)
                {
                    var p = new Vector3(origin.x + (i + 0.5f) * cell, 0.05f, origin.y + (j + 0.5f) * cell);
                    solid[i, j] = Physics.CheckSphere(p, cell * 0.55f, mask, QueryTriggerInteraction.Ignore) ? 1f : 0f;
                }
            // distance to the nearest solid cell (two-pass chamfer), in metres
            var d = new float[N, N];
            const float INF = 1e6f;
            for (int j = 0; j < N; j++) for (int i = 0; i < N; i++) d[i, j] = solid[i, j] > 0 ? 0f : INF;
            float a = cell, b = cell * 1.4142f;
            for (int j = 0; j < N; j++)
                for (int i = 0; i < N; i++)
                {
                    float v = d[i, j];
                    if (i > 0) v = Mathf.Min(v, d[i - 1, j] + a);
                    if (j > 0) v = Mathf.Min(v, d[i, j - 1] + a);
                    if (i > 0 && j > 0) v = Mathf.Min(v, d[i - 1, j - 1] + b);
                    if (i < N - 1 && j > 0) v = Mathf.Min(v, d[i + 1, j - 1] + b);
                    d[i, j] = v;
                }
            for (int j = N - 1; j >= 0; j--)
                for (int i = N - 1; i >= 0; i--)
                {
                    float v = d[i, j];
                    if (i < N - 1) v = Mathf.Min(v, d[i + 1, j] + a);
                    if (j < N - 1) v = Mathf.Min(v, d[i, j + 1] + a);
                    if (i < N - 1 && j < N - 1) v = Mathf.Min(v, d[i + 1, j + 1] + b);
                    if (i > 0 && j < N - 1) v = Mathf.Min(v, d[i - 1, j + 1] + b);
                    d[i, j] = v;
                }
            var tex = new Texture2D(N, N, TextureFormat.R8, false, true);
            var px = new Color32[N * N];
            for (int j = 0; j < N; j++)
                for (int i = 0; i < N; i++)
                {
                    float f = solid[i, j] > 0 ? 1f : Mathf.Clamp01(1f - d[i, j] / 0.9f);
                    byte v = (byte)(Mathf.SmoothStep(0f, 1f, f) * 255);
                    px[j * N + i] = new Color32(v, v, v, 255);
                }
            tex.SetPixels32(px);
            tex.Apply();
            Directory.CreateDirectory("Assets/Saltmoss/Generated");
            string path = "Assets/Saltmoss/Generated/shore_foam.png";
            File.WriteAllBytes(path, tex.EncodeToPNG());
            AssetDatabase.ImportAsset(path);
            if (AssetImporter.GetAtPath(path) is TextureImporter ti)
            {
                ti.sRGBTexture = false;
                ti.wrapMode = TextureWrapMode.Clamp;
                ti.textureCompression = TextureImporterCompression.Uncompressed;
                ti.mipmapEnabled = true;
                ti.SaveAndReimport();
            }
            var mat = sea.seaMaterial;
            mat.SetTexture("_ShoreFoam", AssetDatabase.LoadAssetAtPath<Texture2D>(path));
            mat.SetVector("_ShoreRect", new Vector4(origin.x, origin.y, size, size));
            EditorUtility.SetDirty(mat);
            Debug.Log("[World] shore foam baked");
        }
    }
}
