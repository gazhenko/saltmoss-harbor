using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace Saltmoss
{
    /// <summary>
    /// The clay gauge used by the deck jobs: a vertical slab with a coloured target band, a needle, a progress bar and
    /// a hint line. The winch, the dredge chain and the reel all drive it.
    /// </summary>
    public class MiniGameUI : MonoBehaviour
    {
        public static MiniGameUI I { get; private set; }

        CanvasGroup group;
        RectTransform gauge, band, needle, fill, marker;
        Image bandImg, needleImg;
        TextMeshProUGUI title, hint, top, bottom;
        const float H = 520f;

        public static MiniGameUI Ensure()
        {
            if (I != null) return I;
            var go = new GameObject("MiniGameUI");
            DontDestroyOnLoad(go);
            I = go.AddComponent<MiniGameUI>();
            I.Build();
            return I;
        }

        void Build()
        {
            var c = ClayUI.Canvas("MiniCanvas", 40, transform);
            group = c.gameObject.AddComponent<CanvasGroup>();
            group.alpha = 0f;
            var root = c.transform;
            var panel = ClayUI.Panel("Panel", root, "panel_cream", new Vector2(1f, 0.5f), new Vector2(-80f, 30f), new Vector2(380f, 820f), null, new Vector2(1f, 0.5f));
            title = ClayUI.Text("Title", panel.transform, "", 34f, ClayUI.Ink, TextAlignmentOptions.Top, true);
            title.margin = new Vector4(16, 26, 16, 0);
            var back = ClayUI.Panel("Gauge", panel.transform, "bar_back", new Vector2(0.5f, 0.5f), new Vector2(-30f, 20f), new Vector2(84f, H));
            gauge = back.rectTransform;
            bandImg = ClayUI.Panel("Band", gauge, "bar_fill", new Vector2(0.5f, 0f), Vector2.zero, new Vector2(70f, 100f), new Color(0.45f, 0.78f, 0.45f), new Vector2(0.5f, 0.5f));
            band = bandImg.rectTransform;
            needleImg = ClayUI.Panel("Needle", gauge, "tag", new Vector2(0.5f, 0f), Vector2.zero, new Vector2(120f, 30f), ClayUI.Red, new Vector2(0.5f, 0.5f));
            needle = needleImg.rectTransform;
            marker = ClayUI.Panel("Marker", gauge, "dot", new Vector2(1f, 0f), new Vector2(30f, 0f), new Vector2(40f, 40f)).rectTransform;
            var pb = ClayUI.Panel("Progress", panel.transform, "bar_back", new Vector2(0.5f, 0.5f), new Vector2(80f, 20f), new Vector2(40f, H));
            fill = ClayUI.Panel("Fill", pb.transform, "bar_fill", new Vector2(0.5f, 0f), new Vector2(0f, 4f), new Vector2(30f, 0f), null, new Vector2(0.5f, 0f)).rectTransform;
            top = ClayUI.Text("Top", panel.transform, "", 22f, ClayUI.Muted, TextAlignmentOptions.TopLeft);
            top.margin = new Vector4(24, 80, 0, 0);
            bottom = ClayUI.Text("Bottom", panel.transform, "", 22f, ClayUI.Muted, TextAlignmentOptions.BottomLeft);
            bottom.margin = new Vector4(24, 0, 0, 150);
            hint = ClayUI.Text("Hint", panel.transform, "", 22f, ClayUI.Ink, TextAlignmentOptions.Bottom);
            hint.margin = new Vector4(26, 0, 26, 34);
        }

        public void Show(string t, string h, string topLabel = "", string bottomLabel = "")
        {
            title.text = t;
            hint.text = h;
            top.text = topLabel;
            bottom.text = bottomLabel;
            group.alpha = 1f;
            marker.gameObject.SetActive(false);
        }

        public void Hide() => group.alpha = 0f;

        /// <summary>All values 0..1 from the bottom of the gauge.</summary>
        public void Set(float bandCentre, float bandWidth, float needleAt, float progress, bool inBand)
        {
            if (!ClayClock.SteppedThisFrame && ClayClock.Fps > 0) return;   // the gauge is clay too: it moves on twos
            band.anchoredPosition = new Vector2(0f, bandCentre * H);
            band.sizeDelta = new Vector2(70f, Mathf.Max(20f, bandWidth * H));
            band.gameObject.SetActive(bandWidth > 0f);
            needle.anchoredPosition = new Vector2(0f, Mathf.Clamp01(needleAt) * H);
            needleImg.color = inBand ? new Color(0.35f, 0.62f, 0.3f) : ClayUI.Red;
            fill.sizeDelta = new Vector2(30f, Mathf.Clamp01(progress) * (H - 8f));
        }

        public void Marker(float at, bool on)
        {
            marker.gameObject.SetActive(on);
            marker.anchoredPosition = new Vector2(30f, Mathf.Clamp01(at) * H);
        }

        public void Hint(string h) => hint.text = h;
    }
}
