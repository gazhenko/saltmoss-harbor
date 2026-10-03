using System.Collections;
using System.Collections.Generic;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace Saltmoss
{
    /// <summary>
    /// "You caught a herring!" — the catch held up to the camera, Animal Crossing style: the clay model turning on a
    /// sunburst card, its name in big clay letters, Pip's little quip (with voice blips), a NEW! stamp the first time.
    /// Queues if several things land at once (a full crab pot).
    /// </summary>
    public class CatchReveal : MonoBehaviour
    {
        public static CatchReveal I { get; private set; }
        public static bool Showing { get; private set; }

        Canvas canvas;
        CanvasGroup group;
        RawImage view;
        RectTransform card, burst, stamp;
        TextMeshProUGUI title, quip, price;
        readonly Queue<(ItemDef d, bool first)> queue = new Queue<(ItemDef, bool)>();
        bool running;

        public static CatchReveal Ensure()
        {
            if (I != null) return I;
            var go = new GameObject("CatchReveal");
            DontDestroyOnLoad(go);
            I = go.AddComponent<CatchReveal>();
            I.Build();
            GameState.Caught += (d, first) => I.Enqueue(d, first);
            return I;
        }

        void Build()
        {
            canvas = ClayUI.Canvas("CatchCanvas", 60, transform);
            group = canvas.gameObject.AddComponent<CanvasGroup>();
            group.alpha = 0f;
            var root = canvas.transform;
            var dim = ClayUI.Fill("Dim", root);
            dim.gameObject.AddComponent<Image>().color = new Color(0.08f, 0.06f, 0.05f, 0.45f);
            burst = ClayUI.Rect("Burst", root, new Vector2(0.5f, 0.56f), new Vector2(0.5f, 0.56f), Vector2.zero, new Vector2(820f, 820f));
            for (int i = 0; i < 12; i++)
            {
                var ray = ClayUI.Rect("Ray" + i, burst, new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(120f, 420f), new Vector2(0.5f, 0f));
                ray.localRotation = Quaternion.Euler(0, 0, i * 30f);
                var img = ray.gameObject.AddComponent<Image>();
                img.sprite = UIBank.I.Get("panel_sand");
                img.type = Image.Type.Sliced;
                img.color = i % 2 == 0 ? new Color(0.98f, 0.82f, 0.45f) : new Color(0.98f, 0.9f, 0.7f);
            }
            var disc = ClayUI.Panel("Disc", root, "panel_cream", new Vector2(0.5f, 0.56f), Vector2.zero, new Vector2(600f, 600f));
            card = disc.rectTransform;
            var v = ClayUI.Fill("View", card, 30f);
            view = v.gameObject.AddComponent<RawImage>();
            var banner = ClayUI.Panel("Title", root, "tag", new Vector2(0.5f, 0.23f), Vector2.zero, new Vector2(960f, 130f), ClayUI.Red);
            title = ClayUI.Text("Text", banner.transform, "", 56f, ClayUI.Cream, TextAlignmentOptions.Center, true);
            title.margin = new Vector4(30, 8, 30, 20);
            var q = ClayUI.Panel("Quip", root, "panel_paper", new Vector2(0.5f, 0.1f), Vector2.zero, new Vector2(1100f, 110f));
            quip = ClayUI.Text("Text", q.transform, "", 32f, ClayUI.Ink, TextAlignmentOptions.Center);
            quip.margin = new Vector4(30, 12, 30, 18);
            var pr = ClayUI.Panel("Price", root, "panel_teal", new Vector2(0.5f, 0.56f), new Vector2(250f, -250f), new Vector2(230f, 90f));
            price = ClayUI.Text("Text", pr.transform, "", 34f, ClayUI.Cream, TextAlignmentOptions.Center, true);
            price.margin = new Vector4(10, 8, 10, 16);
            var st = ClayUI.Panel("New", root, "stamp", new Vector2(0.5f, 0.56f), new Vector2(-250f, 230f), new Vector2(170f, 170f));
            stamp = st.rectTransform;
            var nt = ClayUI.Text("Text", stamp, "NEW!", 44f, ClayUI.Cream, TextAlignmentOptions.Center, true);
            nt.margin = new Vector4(0, 0, 0, 10);
            stamp.localRotation = Quaternion.Euler(0, 0, 14f);
        }

        /// <summary>Close the reveal at once (trailer cuts).</summary>
        public void Abort()
        {
            if (!running) return;
            StopAllCoroutines();
            queue.Clear();
            ItemStage.I?.Clear();
            group.alpha = 0f;
            PlayerController.LockCount = Mathf.Max(0, PlayerController.LockCount - 1);
            Showing = false;
            running = false;
        }

        public void Enqueue(ItemDef d, bool first)
        {
            if (d == null) return;
            queue.Enqueue((d, first));
            if (!running) StartCoroutine(Run());
        }

        IEnumerator Run()
        {
            running = true;
            Showing = true;
            PlayerController.LockCount++;
            while (queue.Count > 0)
            {
                var (d, first) = queue.Dequeue();
                var stage = ItemStage.Ensure();
                stage.ShowLive(d);
                view.texture = stage.Live;
                title.text = (d.kind == Kind.Treasure ? "You found " : d.kind == Kind.Junk ? "You fished up " : "You caught ") + Article(d.name) + "!";
                quip.text = "";
                price.transform.parent.gameObject.SetActive(d.Sellable);
                price.text = $"{d.price} SD";
                stamp.gameObject.SetActive(first);
                AudioDirector.I?.Jingle(d.legendary ? "jingle_treasure" : d.kind == Kind.Treasure ? "jingle_treasure" : d.price >= 100 ? "jingle_catch_big" : "jingle_catch_small");
                float t = 0f;
                // pop in
                while (t < 0.3f)
                {
                    t += Time.unscaledDeltaTime;
                    group.alpha = Mathf.Clamp01(t / 0.2f);
                    float s = Mathf.Lerp(0.4f, 1f, Ease(t / 0.3f));
                    card.localScale = Vector3.one * s;
                    yield return null;
                }
                // Pip's quip, typed with voice blips
                string q = d.caught ?? "";
                for (int i = 0; i <= q.Length; i++)
                {
                    quip.text = q.Substring(0, i);
                    if (i > 0 && char.IsLetter(q[i - 1])) VoiceBlips.I?.Speak("pip", q[i - 1], 0.1f, 0.2f);
                    if (GameInput.Confirm.WasPressedThisFrame()) { quip.text = q; break; }
                    yield return new WaitForSecondsRealtime(i > 0 && ".!?".IndexOf(q[i - 1]) >= 0 ? 0.18f : 0.028f);
                }
                float hold = 0f;
                while (hold < 0.5f || !GameInput.Confirm.WasPressedThisFrame())
                {
                    hold += Time.unscaledDeltaTime;
                    if (ClayClock.SteppedThisFrame || Time.timeScale == 0f) burst.localRotation = Quaternion.Euler(0, 0, Time.unscaledTime * 12f);
                    if (hold > 6f && DevCapture.Active) break;
                    yield return null;
                }
                AudioDirector.UI("dialogue_next", 0.5f);
                stage.Clear();
                if (queue.Count == 0)
                {
                    for (float f = 0; f < 0.2f; f += Time.unscaledDeltaTime) { group.alpha = 1f - f / 0.2f; yield return null; }
                    group.alpha = 0f;
                }
            }
            PlayerController.LockCount = Mathf.Max(0, PlayerController.LockCount - 1);
            Showing = false;
            running = false;
        }

        static float Ease(float x) { x = Mathf.Clamp01(x); return 1f + 2.70158f * Mathf.Pow(x - 1f, 3f) + 1.70158f * Mathf.Pow(x - 1f, 2f); }

        static string Article(string name)
        {
            if (name.StartsWith("Gold Doubloons") || name.EndsWith("s")) return name;
            return ("AEIOU".IndexOf(char.ToUpperInvariant(name[0])) >= 0 ? "an " : "a ") + name;
        }
    }
}
