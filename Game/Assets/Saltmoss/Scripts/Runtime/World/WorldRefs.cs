using UnityEngine;

namespace Saltmoss
{
    /// <summary>Scene anchors the generated world hands to runtime systems (filled in by WorldBuilder).</summary>
    public class WorldRefs : MonoBehaviour
    {
        public static WorldRefs I { get; private set; }
        public Transform playerSpawn, pipDoor, board, shopStand, museumDoor, titleCam, titleLook;
        public Transform[] titleShots = new Transform[0];
        void Awake() { I = this; }
    }
}
