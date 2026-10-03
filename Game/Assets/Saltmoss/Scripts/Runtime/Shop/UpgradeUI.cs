using System;
using System.Collections.Generic;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace Saltmoss
{
    /// <summary>Walter's boatyard list and Nell's shop improvements: clay cards with a price and a Buy button.</summary>
    public class UpgradeUI : MonoBehaviour
    {
        static UpgradeUI inst;
        Canvas canvas;
        RectTransform list;
        TextMeshProUGUI header, money;
        readonly List<GameObject> rows = new List<GameObject>();
        Action done;
        bool shopSide, open;
        float openedAt;
        public static event Action<string> Bought;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Register()
        {
            GameFlow.On("upgrades", (args, d) => Open(args.Length > 1 && args[1] == "shop", d));
        }

        static void Open(bool shop, Action onDone)
        {
            if (inst == null)
            {
                var go = new GameObject("UpgradeUI");
                DontDestroyOnLoad(go);
                inst = go.AddComponent<UpgradeUI>();
                inst.Build();
            }
            inst.shopSide = shop;
            inst.done = onDone;
            inst.Show();
        }

        void Build()
        {
            canvas = ClayUI.Canvas("UpgradeCanvas", 45, transform);
            var panel = ClayUI.Panel("Panel", canvas.transform, "panel_cream", new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(1240f, 820f));
            header = ClayUI.Text("Title", panel.transform, "", 50f, ClayUI.Red, TextAlignmentOptions.Top, true);
            header.margin = new Vector4(30, 30, 30, 0);
            money = ClayUI.Text("Money", panel.transform, "", 32f, ClayUI.Ink, TextAlignmentOptions.TopRight, true);
            money.margin = new Vector4(30, 44, 60, 0);
            list = ClayUI.Rect("List", panel.transform, new Vector2(0.5f, 1f), new Vector2(0.5f, 1f), new Vector2(0f, -120f), new Vector2(1120f, 560f), new Vector2(0.5f, 1f));
            var vl = list.gameObject.AddComponent<VerticalLayoutGroup>();
            vl.spacing = 14f;
            vl.childControlHeight = false;
            vl.childControlWidth = true;
            vl.childForceExpandHeight = false;
            ClayUI.Button("Close", panel.transform, "Thanks!", new Vector2(0.5f, 0f), new Vector2(0f, 40f), new Vector2(360f, 86f), Close, 32f);
            canvas.gameObject.SetActive(false);
        }

        void Show()
        {
            open = true;
            openedAt = Time.unscaledTime;
            canvas.gameObject.SetActive(true);
            DialogueUI.Suspended = true;
            if (GameFlow.I != null) GameFlow.I.InMenu = true;
            header.text = shopSide ? "Fixing up the Salty Puffin" : "Walter's Boatyard";
            Fill();
        }

        void Fill()
        {
            foreach (var r in rows) Destroy(r);
            rows.Clear();
            money.text = $"{GameState.D.money:N0} SD";
            Button first = null;
            int shown = 0;
            foreach (var u in Upgrades.All)
            {
                if (u.shop != shopSide || !Upgrades.Available(u)) continue;
                if (++shown > 5) break;
                var row = ClayUI.Panel("Row", list, "panel_paper", new Vector2(0.5f, 1f), Vector2.zero, new Vector2(1120f, 100f));
                var le = row.gameObject.AddComponent<LayoutElement>();
                le.preferredHeight = 100f;
                var t = ClayUI.Text("Text", row.transform, $"<b>{u.name}</b>  <size=80%><color=#7a6858>{u.desc}</color></size>", 30f, ClayUI.Ink, TextAlignmentOptions.Left);
                t.margin = new Vector4(30, 10, 330, 14);
                bool afford = GameState.D.money >= u.cost;
                var uu = u;
                var b = ClayUI.Button("Buy", row.transform, $"{u.cost:N0} SD", new Vector2(1f, 0.5f), new Vector2(-160f, 2f), new Vector2(280f, 76f), () => Buy(uu), 30f);
                b.GetComponent<Image>().color = afford ? Color.white : new Color(0.75f, 0.72f, 0.68f);
                rows.Add(row.gameObject);
                if (first == null) first = b;
            }
            if (shown == 0)
            {
                var row = ClayUI.Panel("Row", list, "panel_paper", new Vector2(0.5f, 1f), Vector2.zero, new Vector2(1120f, 100f));
                row.gameObject.AddComponent<LayoutElement>().preferredHeight = 100f;
                ClayUI.Text("Text", row.transform, "Everything's done! She's in fine shape.", 32f, ClayUI.Ink, TextAlignmentOptions.Center).margin = new Vector4(20, 10, 20, 14);
                rows.Add(row.gameObject);
            }
            ClayUI.Select(first != null ? first : canvas.GetComponentInChildren<Button>());
        }

        void Buy(UpgradeDef u)
        {
            if (Time.unscaledTime - openedAt < 0.25f) return;
            if (!GameState.Spend(u.cost))
            {
                AudioDirector.UI("ui_error");
                GameState.Say($"Not enough sand dollars for the {u.name} yet.");
                return;
            }
            GameState.D.upgrades.Add(u.id);
            GameState.Notify();
            AudioDirector.I?.Jingle("jingle_upgrade");
            AudioDirector.UI("register", 0.7f);
            GameState.Say($"{u.name}: done!");
            PotsVisual.Refresh();
            ShopCounter.I?.RefreshDisplay();
            Restoration.I?.Apply();
            Bought?.Invoke(u.id);
            Fill();
        }

        void Close()
        {
            if (!open) return;
            open = false;
            canvas.gameObject.SetActive(false);
            DialogueUI.Suspended = false;
            if (GameFlow.I != null) GameFlow.I.InMenu = false;
            var d = done;
            done = null;
            d?.Invoke();
        }

        void Update()
        {
            if (open && GameInput.Back.WasPressedThisFrame()) Close();
        }
    }
}
