import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

Item {
    id: page

    ListModel { id: logModel }

    function append(line) {
        if (logModel.count > 800)
            logModel.remove(0, logModel.count - 800);
        logModel.append({ "line": line });
        logView.positionViewAtEnd();
    }

    Connections {
        target: bridge
        function onLogLine(line) { page.append(line); }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 26
        anchors.rightMargin: 22
        anchors.topMargin: 4
        anchors.bottomMargin: 16
        spacing: 10

        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            Text {
                text: "游戏输出"
                font.pixelSize: 13
                font.weight: Font.DemiBold
                color: theme.text1
            }
            Text {
                text: logModel.count + " 行"
                font.pixelSize: 11
                color: theme.text3
            }
            Item { Layout.fillWidth: true }
            SproutButton {
                text: "清空"
                primary: false
                implicitHeight: 32
                fontSize: 12
                onClicked: logModel.clear()
            }
            SproutButton {
                text: "打开日志目录"
                primary: false
                implicitHeight: 32
                fontSize: 12
                onClicked: bridge.openPath(bridge.appDataDir())
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: 12
            color: theme.surfaceAlt
            clip: true

            ListView {
                id: logView
                anchors.fill: parent
                anchors.margins: 12
                clip: true
                spacing: 1
                model: logModel
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                delegate: Text {
                    required property string line
                    width: ListView.view.width
                    text: line
                    font.family: "Consolas"
                    font.pixelSize: 12
                    color: line.indexOf("[Sprout]") === 0 ? theme.accent : theme.text2
                    wrapMode: Text.NoWrap
                    elide: Text.ElideRight
                }
            }

            Text {
                anchors.centerIn: parent
                visible: logModel.count === 0
                text: "启动游戏后，日志会实时出现在这里"
                font.pixelSize: 12
                color: theme.text3
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 38
                radius: 10
                color: theme.card
                border.width: 1
                border.color: cmdField.activeFocus ? theme.accent : theme.border

                Text {
                    anchors.left: parent.left
                    anchors.leftMargin: 12
                    anchors.verticalCenter: parent.verticalCenter
                    visible: cmdField.text.length === 0
                    text: bridge.running ? "输入指令，例如 gamemode creative" : "游戏启动后可在此发送指令"
                    font.pixelSize: 12
                    color: theme.text3
                }

                TextField {
                    id: cmdField
                    anchors.fill: parent
                    anchors.leftMargin: 12
                    anchors.rightMargin: 12
                    background: Item {}
                    color: theme.text1
                    font.pixelSize: 13
                    enabled: bridge.running
                    verticalAlignment: TextInput.AlignVCenter
                    onAccepted: {
                        if (text.trim().length > 0) {
                            bridge.sendCommand(text.trim());
                            text = "";
                        }
                    }
                }
            }

            SproutButton {
                text: "发送"
                primary: true
                active: bridge.running
                implicitHeight: 38
                fontSize: 13
                onClicked: {
                    if (cmdField.text.trim().length > 0) {
                        bridge.sendCommand(cmdField.text.trim());
                        cmdField.text = "";
                    }
                }
            }
        }
    }
}
