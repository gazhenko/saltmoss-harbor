using UnityEngine;

namespace Saltmoss
{
    /// <summary>The painted cyclorama: a huge sphere drawn from the inside that stays centred on the camera.</summary>
    [ExecuteAlways]
    public class Backdrop : MonoBehaviour
    {
        public float radius = 2400f;

        void LateUpdate()
        {
            var cam = Camera.main;
            if (cam != null) transform.position = cam.transform.position;
            transform.localScale = Vector3.one * radius * 2f;
        }
    }
}
