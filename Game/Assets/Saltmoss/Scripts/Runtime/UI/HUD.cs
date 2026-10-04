using System.Collections.Generic;
using System.Text.RegularExpressions;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace Saltmoss
{
    /// <summary>
    /// On-screen clay bits: the day/clock/weather slab, sand dollars, hold and pots at sea, the current task, the
    /// interaction prompt with the right key or button, toasts, and the big banner when entering fishing grounds.
    /// </summary>
    public class HUD : MonoBehaviour
    {
        public static HUD I { get; private set; }

        Canvas canvas;
        CanvasGroup group;
        TextMeshProUGUI clockText, moneyText, holdText, taskText, promptText, promptKey, banner, bannerSub;
        RectTransform promptRt, bannerRt, holdRt, toastRoot, clockHand;
        Image promptCap;
        readonly List<(RectTransform rt, CanvasGroup g, float t)> toasts = new List<(RectTransform, CanvasGroup, float)>();
        float bannerT = 99f;
        int shownMoney = -1;
        float moneyAnim;
        public static string Task = "";
        /// <summary>Clean frames for screenshots and the trailer (-noHud).</summary>
        public static bool ForceHidden = CommandLine.Has("-noHud");
        const float PromptH = 70f, CapH = 50f, PromptPad = 18f;
        public static string ActionPrompt;        // set every frame by sea systems (e.g. "Cast line")
        public static string ActionKey;           // "UseTool" or "Interact"

        public static HUD Ensure()
        {
            if (I != null) return I;
            var go = new GameObject("HUD");
            DontDestroyOnLoad(go);
            I = go.AddComponent<HUD>();
            I.Build();
            return I;
        }

        void Build()
        {
            canvas = ClayUI.Canvas("HUDCanvas", 10, transform);
            group = canvas.gameObject.AddComponent<CanvasGroup>();
            var root = canvas.transform;

            var clock = ClayUI.Panel("Clock", root, "panel_cream", new Vector2(0f, 1f), new Vector2(30f, -26f), new Vector2(430f, 120f), null, new Vector2(0f, 1f));
            var icon = ClayUI.Panel("ClockIcon", clock.transform, "clock", new Vector2(0f, 0.5f), new Vector2(66f, 2f), new Vector2(92f, 92f));
            clockHand = ClayUI.Rect("Hand", icon.transform, new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(8f, 30f), new Vector2(0.5f, 0f));
            clockHand.gameObject.AddComponent<Image>().color = ClayUI.Red;
            clockText = ClayUI.Text("Text", clock.transform, "", 32f, ClayUI.Ink, TextAlignmentOptions.Left, true);
            clockText.margin = new Vector4(122, 18, 20, 18);
            clockText.lineSpacing = -14f;

            var task = ClayUI.Panel("Task", root, "panel_paper", new Vector2(0f, 1f), new Vector2(34f, -150f), new Vector2(520f, 86f), null, new Vector2(0f, 1f));
            taskText = ClayUI.Text("Text", task.transform, "", 26f, ClayUI.Ink, TextAlignmentOptions.Left);
            taskText.margin = new Vector4(26, 12, 22, 16);

            var money = ClayUI.Panel("Money", root, "panel_cream", new Vector2(1f, 1f), new Vector2(-30f, -26f), new Vector2(300f, 100f), null, new Vector2(1f, 1f));
            ClayUI.Panel("Coin", money.transform, "coin", new Vector2(0f, 0.5f), new Vector2(58f, 2f), new Vector2(84f, 84f));
            moneyText = ClayUI.Text("Text", money.transform, "0", 42f, ClayUI.Ink, TextAlignmentOptions.Right, true);
            moneyText.margin = new Vector4(100, 14, 30, 18);

            var hold = ClayUI.Panel("Hold", root, "panel_teal", new Vector2(1f, 1f), new Vector2(-30f, -134f), new Vector2(300f, 92f), null, new Vector2(1f, 1f));
            holdRt = hold.rectTransform;
            holdText = ClayUI.Text("Text", hold.transform, "", 28f, ClayUI.Cream, TextAlignmentOptions.Center, true);
            holdText.margin = new Vector4(16, 10, 16, 16);
            holdText.lineSpacing = -10f;

            var prompt = ClayUI.Panel("Prompt", root, "panel_cream", new Vector2(0.5f, 0f), new Vector2(0f, 360f), new Vector2(300f, PromptH), null, new Vector2(0.5f, 0f));
            promptRt = prompt.rectTransform;
            promptKey = ClayUI.Prompt(prompt.transform, new Vector2(0f, 0.5f), new Vector2(PromptPad + CapH * 0.5f, 2f), out promptCap);
            promptCap.rectTransform.sizeDelta = new Vector2(CapH, CapH);
            promptKey.fontSizeMax = 25;
            promptText = ClayUI.Text("Text", prompt.transform, "", 27f, ClayUI.Ink, TextAlignmentOptions.Left, true);
            promptText.textWrappingMode = TextWrappingModes.NoWrap;
            promptText.margin = Vector4.zero;

            bannerRt = ClayUI.Rect("Banner", root, new Vector2(0.5f, 0.72f), new Vector2(0.5f, 0.72f), Vector2.zero, new Vector2(1400f, 220f));
            banner = ClayUI.Text("Title", bannerRt, "", 110f, ClayUI.Cream, TextAlignmentOptions.Center, true);
            banner.outlineWidth = 0.22f;
            banner.outlineColor = new Color32(0x3a, 0x2a, 0x22, 255);
            bannerSub = ClayUI.Text("Sub", bannerRt, "", 40f, ClayUI.Cream, TextAlignmentOptions.Bottom, false);
            bannerSub.rectTransform.offsetMin = new Vector2(0, -70);
            bannerSub.outlineWidth = 0.2f;
            bannerSub.outlineColor = new Color32(0x3a, 0x2a, 0x22, 255);

            toastRoot = ClayUI.Rect("Toasts", root, new Vector2(0.5f, 1f), new Vector2(0.5f, 1f), new Vector2(0f, -40f), new Vector2(900f, 400f), new Vector2(0.5f, 1f));
            GameState.Toast += Toast;
        }

        void OnDestroy() => GameState.Toast -= Toast;

        public void Toast(string msg)
        {
            var p = ClayUI.Panel("Toast", toastRoot, "panel_paper", new Vector2(0.5f, 1f), Vector2.zero, new Vector2(860f, 84f), null, new Vector2(0.5f, 1f));
            var t = ClayUI.Text("Text", p.transform, msg, 30f, ClayUI.Ink, TextAlignmentOptions.Center);
            t.margin = new Vector4(26, 10, 26, 16);
            t.textWrappingMode = TextWrappingModes.Normal;
            var g = p.gameObject.AddComponent<CanvasGroup>();
            toasts.Insert(0, (p.rectTransform, g, 0f));
            AudioDirector.UI("ui_open", 0.4f);
        }

        public void Banner(string title, string sub)
        {
            banner.text = title;
            bannerSub.text = sub;
            bannerT = 0f;
        }

        public void Visible(bool on) { ForceHidden = !on; group.alpha = on ? 1f : 0f; }

        void Update()
        {
            var D = GameState.D;
            bool hide = DialogueRunner.Active || (GameFlow.I != null && GameFlow.I.InMenu) || TitleScreen.Showing || ForceHidden;
            group.alpha = Mathf.MoveTowards(group.alpha, hide ? 0f : 1f, Time.unscaledDeltaTime * 5f);

            clockText.text = $"Day {D.day} · {GameFlow.Clock(D.hour)}\n<size=70%>{GameFlow.WeatherName(D.weather)}</size>";
            clockHand.localRotation = Quaternion.Euler(0, 0, -(D.hour % 12f) / 12f * 360f);
            if (shownMoney != D.money)
            {
                if (shownMoney >= 0) moneyAnim = 1f;
                shownMoney = D.money;
                moneyText.text = D.money.ToString("N0");
            }
            moneyAnim = Mathf.MoveTowards(moneyAnim, 0f, Time.unscaledDeltaTime * 3f);
            moneyText.transform.localScale = Vector3.one * (1f + moneyAnim * 0.15f);

            bool atSea = BoatController.I != null && BoatController.I.Aboard;
            holdRt.gameObject.SetActive(atSea);
            if (atSea) holdText.text = $"Hold {GameState.Count(D.hold)}/{GameState.HoldCapacity}\n<size=75%>Pots aboard {Mathf.Max(0, CrabPots.OnDeck)}/{GameState.PotCount}</size>";
            taskText.transform.parent.gameObject.SetActive(!string.IsNullOrEmpty(Task));
            if (taskText.text != Task)
            {
                taskText.text = Task;
                taskText.ForceMeshUpdate();
                var rt = (RectTransform)taskText.transform.parent;
                rt.sizeDelta = new Vector2(520f, Mathf.Max(86f, taskText.preferredHeight + 34f));
            }

            // prompt: sea action first, else whatever Pip is facing
            string text = null, keyName = null;
            if (!string.IsNullOrEmpty(ActionPrompt)) { text = ActionPrompt; keyName = ActionKey; }
            else if (PlayerController.I != null && PlayerController.I.Focus != null) { text = PlayerController.I.Focus.Prompt; keyName = "Interact"; }
            ActionPrompt = null;
            bool showPrompt = text != null && !hide;
            promptRt.gameObject.SetActive(showPrompt);
            if (showPrompt)
            {
                promptText.text = text;
                var bind = keyName == "UseTool" ? Bind.UseTool : keyName == "Run" ? Bind.Run : Bind.Interact;
                string key = GameInput.Label(bind);
                promptKey.text = key;
                // size the cap to what it shows: controller glyphs carry colour/size tags, so count visible characters
                int shown = Regex.Replace(key, "<[^>]*>", "").Length;
                float capW = shown <= 2 ? CapH : 22f + shown * 15f;
                promptCap.rectTransform.sizeDelta = new Vector2(capW, CapH);
                promptCap.rectTransform.anchoredPosition = new Vector2(PromptPad + capW * 0.5f, 2f);
                var trt = promptText.rectTransform;
                trt.offsetMin = new Vector2(PromptPad + capW + 14f, 6f);
                trt.offsetMax = new Vector2(-PromptPad, -6f);
                float tw = promptText.GetPreferredValues(text, 2000f, PromptH).x;
                promptRt.sizeDelta = new Vector2(Mathf.Clamp(tw + capW + 14f + PromptPad * 2f + 12f, 180f, 900f), PromptH);
            }

            // banner: pop in, hold, fade
            bannerT += Time.unscaledDeltaTime;
            float a = bannerT < 0.25f ? bannerT / 0.25f : bannerT < 2.6f ? 1f : Mathf.Clamp01(1f - (bannerT - 2.6f) / 0.6f);
            banner.alpha = bannerSub.alpha = a;
            if (ClayClock.SteppedThisFrame) bannerRt.localScale = Vector3.one * (1f + Mathf.Max(0f, 0.25f - bannerT) * 0.8f);

            // toasts stack and fade after 3.5 s
            for (int i = toasts.Count - 1; i >= 0; i--)
            {
                var (rt, g, t) = toasts[i];
                t += Time.unscaledDeltaTime;
                toasts[i] = (rt, g, t);
                rt.anchoredPosition = Vector2.Lerp(rt.anchoredPosition, new Vector2(0f, -i * 94f), Time.unscaledDeltaTime * 10f);
                g.alpha = t < 0.2f ? t / 0.2f : t > 3.5f ? Mathf.Clamp01(1f - (t - 3.5f) / 0.5f) : 1f;
                if (t > 4f || i > 3) { Destroy(rt.gameObject); toasts.RemoveAt(i); }
            }
        }
    }
}
