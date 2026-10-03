using System.Collections.Generic;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace Saltmoss
{
    /// <summary>
    /// Little clay speech bubbles that float over things in the world: a fish's "!", a customer's order (icon and
    /// count), a mumbled "Hm-hm!". Screen-space, tracking a world point or transform, popping in on twos.
    /// </summary>
    public class BubbleText : MonoBehaviour
    {
        static BubbleText inst;
        Canvas canvas;

        public class Bubble
        {
            public RectTransform rt;
            public TextMeshProUGUI text;
            public Image icon;
            public Transform follow;
            public Vector3 point, offset;
            public float life, age;
            public bool alive = true;
            public void Close() => life = Mathf.Min(life, age + 0.15f);
        }

        readonly List<Bubble> bubbles = new List<Bubble>();

        static BubbleText Ensure()
        {
            if (inst != null) return inst;
            var go = new GameObject("Bubbles");
            DontDestroyOnLoad(go);
            inst = go.AddComponent<BubbleText>();
            inst.canvas = ClayUI.Canvas("BubbleCanvas", 5, go.transform);
            return inst;
        }

        public static Bubble Show(Vector3 world, string text, float seconds = 2f, Sprite icon = null, Transform follow = null, Vector3? offset = null)
        {
            var b = Ensure();
            bool wide = icon != null || text.Length > 2;
            var img = ClayUI.Panel("Bubble", b.canvas.transform, "bubble", new Vector2(0f, 0f), Vector2.zero, wide ? new Vector2(icon != null ? 210f : 60f + text.Length * 22f, 170f) : new Vector2(130f, 150f), null, new Vector2(0.5f, 0f));
            var t = ClayUI.Text("Text", img.transform, text, icon != null ? 44f : 64f, icon != null ? ClayUI.Ink : ClayUI.Red, icon != null ? TextAlignmentOptions.Right : TextAlignmentOptions.Center, true);
            t.margin = new Vector4(18, 10, icon != null ? 22 : 18, 52);
            Image ic = null;
            if (icon != null)
            {
                ic = ClayUI.Panel("Icon", img.transform, null, new Vector2(0f, 0.5f), new Vector2(70f, 18f), new Vector2(110f, 110f));
                ic.sprite = icon;
                ic.color = Color.white;
                ic.preserveAspect = true;
            }
            var bub = new Bubble { rt = img.rectTransform, text = t, icon = ic, follow = follow, point = world, offset = offset ?? Vector3.zero, life = seconds };
            b.bubbles.Add(bub);
            return bub;
        }

        void LateUpdate()
        {
            var cam = Camera.main;
            if (cam == null) return;
            float scale = canvas.transform.localScale.x;
            for (int i = bubbles.Count - 1; i >= 0; i--)
            {
                var b = bubbles[i];
                b.age += Time.deltaTime;
                if (b.age > b.life || (b.follow == null && b.point == Vector3.zero))
                {
                    Destroy(b.rt.gameObject);
                    b.alive = false;
                    bubbles.RemoveAt(i);
                    continue;
                }
                var w = (b.follow != null ? b.follow.position : b.point) + b.offset;
                var sp = cam.WorldToScreenPoint(w);
                bool visible = sp.z > 0 && !DialogueRunner.Active && !CatchReveal.Showing;
                b.rt.gameObject.SetActive(visible);
                if (!visible) continue;
                b.rt.anchoredPosition = new Vector2(sp.x, sp.y) / scale;
                if (ClayClock.SteppedThisFrame || Time.timeScale == 0f)
                {
                    float pop = b.age < 0.2f ? Mathf.Lerp(0.3f, 1.1f, b.age / 0.2f) : b.life - b.age < 0.15f ? (b.life - b.age) / 0.15f : 1f + Mathf.Sin(b.age * 5f) * 0.03f;
                    b.rt.localScale = Vector3.one * pop * Mathf.Clamp(8f / Mathf.Max(sp.z, 1f), 0.55f, 1.1f);
                }
            }
        }
    }
}
