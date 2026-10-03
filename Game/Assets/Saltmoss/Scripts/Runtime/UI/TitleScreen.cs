using System.Collections;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace Saltmoss
{
    /// <summary>
    /// The title: a slow tabletop dolly around the harbour, the clay logo, and New Game / Continue / Settings / Quit.
    /// </summary>
    public class TitleScreen : MonoBehaviour
    {
        public static bool Showing { get; private set; }
        static TitleScreen inst;
        Canvas canvas;
        CanvasGroup group;
        Image logo;
        TextMeshProUGUI sub;
        RectTransform menu;
        float t;
        int shot;

        public static void Show()
        {
            if (inst == null)
            {
                var go = new GameObject("TitleScreen");
                inst = go.AddComponent<TitleScreen>();
                inst.Build();
            }
            inst.Open();
        }

        void Build()
        {
            canvas = ClayUI.Canvas("TitleCanvas", 75, transform);
            group = canvas.gameObject.AddComponent<CanvasGroup>();
            var root = canvas.transform;
            logo = ClayUI.Panel("Logo", root, "logo", new Vector2(0.5f, 0.72f), Vector2.zero, new Vector2(1100f, 440f));
            logo.preserveAspect = true;
            if (logo.sprite == null)
            {
                logo.color = new Color(0, 0, 0, 0);
                var t = ClayUI.Text("LogoText", logo.transform, "Saltmoss Harbor", 130f, ClayUI.Cream, TextAlignmentOptions.Center, true);
                t.outlineWidth = 0.25f;
                t.outlineColor = new Color32(0x3a, 0x2a, 0x22, 255);
                t.gameObject.AddComponent<TextFx>();
            }
            sub = ClayUI.Text("Sub", root, "", 30f, ClayUI.Cream, TextAlignmentOptions.Bottom);
            sub.rectTransform.offsetMin = new Vector2(0, 26);
            sub.outlineWidth = 0.2f;
            sub.outlineColor = new Color32(0x3a, 0x2a, 0x22, 255);
            menu = ClayUI.Rect("Menu", root, new Vector2(0.5f, 0.28f), new Vector2(0.5f, 0.28f), Vector2.zero, new Vector2(520f, 400f));
            var vl = menu.gameObject.AddComponent<VerticalLayoutGroup>();
            vl.spacing = 14f;
            vl.childControlHeight = false;
            vl.childControlWidth = true;
            vl.childForceExpandHeight = false;
        }

        void Open()
        {
            Showing = true;
            canvas.gameObject.SetActive(true);
            group.alpha = 1f;
            PlayerController.LockCount++;
            GameFlow.ClockRunning = false;
            foreach (Transform c in menu) Destroy(c.gameObject);
            Button first = null;
            if (GameState.HasSave) first = Add("Continue", Continue);
            var ng = Add(GameState.HasSave ? "New game" : "Start", NewGame);
            if (first == null) first = ng;
            Add("Settings", () => { canvas.gameObject.SetActive(false); PauseMenu.OpenSettings(() => { canvas.gameObject.SetActive(true); ClayUI.Select(menu.GetComponentInChildren<Button>()); }); });
            Add("Quit", Application.Quit);
            ClayUI.Select(first);
            sub.text = "a cosy claymation fishing tale · v" + Application.version;
            AudioDirector.I?.Music("title_theme");
            AudioDirector.I?.Ambience("amb_harbor_day");
            if (DayCycle.I != null) { DayCycle.I.frozen = true; DayCycle.I.hour = 17.2f; }
        }

        Button Add(string label, System.Action a)
        {
            var b = ClayUI.Button(label, menu, label, new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(520f, 86f), a, 36f);
            return b;
        }

        void Continue()
        {
            GameState.Load();
            StartCoroutine(Begin(false));
        }

        void NewGame()
        {
            GameState.New();
            StartCoroutine(Begin(true));
        }

        IEnumerator Begin(bool fresh)
        {
            AudioDirector.UI("shop_bell");
            for (float f = 1f; f > 0f; f -= Time.unscaledDeltaTime * 2.5f) { group.alpha = f; yield return null; }
            canvas.gameObject.SetActive(false);
            Showing = false;
            if (DayCycle.I != null) DayCycle.I.frozen = false;
            CameraRig.I?.ClearOverride();
            GameBoot.I?.PlaceForStart(fresh);
            PlayerController.LockCount = Mathf.Max(0, PlayerController.LockCount - 1);
            GameFlow.ClockRunning = true;
            if (fresh)
            {
                // Pip steps off the ferry right in front of Walter
                var w = DialogueRunner.Actor("walter");
                var p = PlayerController.I;
                if (w != null && p != null)
                {
                    var spot = w.root.position + w.root.forward * 2.2f;
                    p.Teleport(spot, Quaternion.LookRotation(w.root.position - spot).eulerAngles.y);
                    CameraRig.I?.SnapBehindTarget();
                }
                yield return new WaitForSeconds(1.0f);
                DialogueRunner.Play("intro", "walter");
            }
            else HUD.I?.Banner($"DAY {GameState.D.day}", GameFlow.WeatherName(GameState.D.weather));
        }

        void Update()
        {
            if (!Showing) return;
            // slow dolly between the title shots
            var refs = WorldRefs.I;
            if (refs == null || refs.titleShots.Length < 2 || CameraRig.I == null) return;
            t += Time.unscaledDeltaTime / 14f;
            if (t >= 1f) { t = 0f; shot = (shot + 1) % refs.titleShots.Length; }
            var a = refs.titleShots[shot];
            var b = refs.titleShots[(shot + 1) % refs.titleShots.Length];
            float e = Mathf.SmoothStep(0f, 1f, t);
            CameraRig.I.SetOverride(Vector3.Lerp(a.position, b.position, e), Quaternion.Slerp(a.rotation, b.rotation, e), 32f);
        }
    }
}
