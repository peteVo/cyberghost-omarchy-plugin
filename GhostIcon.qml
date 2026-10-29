import QtQuick
import QtQuick.Shapes

Item {
  id: root
  required property color color
  property real opticalScale: 1
  implicitWidth: 20
  implicitHeight: 20

  Shape {
    anchors.centerIn: parent
    width: 20
    height: 20
    scale: Math.min(root.width, root.height) / 20 * root.opticalScale
    preferredRendererType: Shape.CurveRenderer
    ShapePath {
      strokeWidth: 0
      fillRule: ShapePath.OddEvenFill
      fillColor: root.color
      PathSvg {
        path: "M3 17.5V8.5a7 7 0 0 1 14 0v9q0 1.6-1.4.5L13 16.5l-2 2q-1 1-2 0l-2-2-2.6 2Q3 19.1 3 17.5Z M8.6 9.5a1.1 1.6 0 1 1-2.2 0a1.1 1.6 0 1 1 2.2 0Z M13.6 9.5a1.1 1.6 0 1 1-2.2 0a1.1 1.6 0 1 1 2.2 0Z"
      }
    }
  }
}
