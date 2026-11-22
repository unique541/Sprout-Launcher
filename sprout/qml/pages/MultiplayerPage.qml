import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

Item {
    id: page

    property string room: ""
    property string secret: ""
    property string peers: ""
    property string portText: "25565"

    function commitPort() {
        var n = parseInt(page.portText, 10);
        if (!isNaN(n) && n > 0 && n <= 65535)
            bridge.setTunnelPort(n);
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 26
        anchors.rightMargin: 22
        anchors.topMargin: 4
        anchors.bottomMargin: 8
        spacing: 12

        // -------------------------------------------------- 状态卡
        Card {
            Layout.fillWidth: true
            Layout.preferredHeight: 112
            corner: 14
            interactive: false

            RowLayout {
                anchors.fill: parent
                anchors.margins: 18
                spacing: 16

                Rectangle {
                    Layout.preferredWidth: 10
                    Layout.preferredHeight: 10
                    radius: 5
                    color: bridge.tunnelRunning ? theme.accent : theme.text3

                    SequentialAnimation on opacity {
                        running: bridge.tunnelRunning
                        loops: Animation.Infinite
                        NumberAnimation { from: 1.0; to: 0.3; duration: 1400; easing.type: Easing.InOutSine }
                        NumberAnimation { from: 0.3; to: 1.0; duration: 1400; easing.type: Easing.InOutSine }
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 5

                    Text {
                        text: bridge.tunnelRunning ? "联机已开启" : "联机未开启"
                        font.pixelSize: 16
                        font.weight: Font.DemiBold
                        color: theme.text1
                    }

                    Text {
                        text: bridge.tunnelRunning
                              ? (bridge.tunnelRoleLabel + " · " + bridge.tunnelBackendLabel
                                 + " · 房间：" + bridge.tunnelRoom
                                 + "    连接地址：" + (bridge.tunnelAddress.length > 0 ? bridge.tunnelAddress : "获取中…"))
                              : "点「创建房间」自己开房，或填好房间信息点「加入房间」"
                        font.pixelSize: 11
                        color: theme.text3
                    }

                    Text {
                        text: bridge.tunnelRunning
                              ? ("游戏端口 " + bridge.tunnelPort + "：朋友在游戏内「多人游戏 → 直接连接」输入上面的连接地址")
                              : "首次使用 P2P / 陶瓦联机需要先获取联机组件（约 20 MB）；局域网直连无需组件"
                        font.pixelSize: 11
                        color: theme.text3
                        elide: Text.ElideRight
                    }
                }

                SproutButton {
                    text: "获取联机组件"
                    primary: false
                    active: !bridge.busy && bridge.tunnelBackend !== "lan"
                    implicitHeight: 34
                    fontSize: 12
                    onClicked: bridge.installP2P()
                }

                SproutButton {
                    text: "停止联机"
                    primary: false
                    active: bridge.tunnelRunning
                    implicitHeight: 34
                    fontSize: 12
                    onClicked: bridge.stopTunnel()
                }
            }
        }

        // -------------------------------------------------- 房间设置
        Card {
            Layout.fillWidth: true
            Layout.preferredHeight: 286
            corner: 14
            interactive: false

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 18
                spacing: 10

                Text {
                    text: "联机方式"
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                    color: theme.text1
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    Repeater {
                        model: bridge.tunnelMethods || []

                        Rectangle {
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.preferredHeight: 58
                            radius: 10
                            color: bridge.tunnelBackend === modelData.id ? theme.accentSoft : theme.surfaceAlt
                            border.width: 1
                            border.color: bridge.tunnelBackend === modelData.id ? theme.accent : "transparent"

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 10
                                spacing: 3

                                Text {
                                    text: modelData.label
                                    font.pixelSize: 12
                                    font.weight: Font.DemiBold
                                    color: bridge.tunnelBackend === modelData.id ? theme.accent : theme.text1
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: modelData.desc
                                    font.pixelSize: 10
                                    color: theme.text3
                                    wrapMode: Text.WordWrap
                                    maximumLineCount: 2
                                    elide: Text.ElideRight
                                }
                            }

                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (!bridge.tunnelRunning)
                                        bridge.setTunnelBackend(modelData.id);
                                }
                            }
                        }
                    }
                }

                Text {
                    text: "房间设置"
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                    color: theme.text1
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 6

                        Text {
                            text: "房间名"
                            font.pixelSize: 11
                            color: theme.text3
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 34
                            radius: 9
                            color: theme.surfaceAlt
                            border.width: 1
                            border.color: roomField.activeFocus ? theme.accent : "transparent"

                            Behavior on border.color { ColorAnimation { duration: 160 } }

                            TextField {
                                id: roomField
                                anchors.fill: parent
                                anchors.leftMargin: 11
                                anchors.rightMargin: 11
                                background: Item {}
                                placeholderText: "例如 sprout-2026"
                                placeholderTextColor: theme.text3
                                color: theme.text1
                                font.pixelSize: 12
                                verticalAlignment: TextInput.AlignVCenter
                                onTextChanged: page.room = text
                            }
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 6

                        Text {
                            text: "房间密钥（可选）"
                            font.pixelSize: 11
                            color: theme.text3
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 34
                            radius: 9
                            color: theme.surfaceAlt
                            border.width: 1
                            border.color: secretField.activeFocus ? theme.accent : "transparent"

                            Behavior on border.color { ColorAnimation { duration: 160 } }

                            TextField {
                                id: secretField
                                anchors.fill: parent
                                anchors.leftMargin: 11
                                anchors.rightMargin: 11
                                background: Item {}
                                placeholderText: "留空表示公开房间"
                                placeholderTextColor: theme.text3
                                color: theme.text1
                                font.pixelSize: 12
                                echoMode: TextInput.Password
                                verticalAlignment: TextInput.AlignVCenter
                                onTextChanged: page.secret = text
                            }
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 6

                        Text {
                            text: "游戏端口（对局域网开放时生成）"
                            font.pixelSize: 11
                            color: theme.text3
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 34
                            radius: 9
                            color: theme.surfaceAlt
                            border.width: 1
                            border.color: portField.activeFocus ? theme.accent : "transparent"

                            Behavior on border.color { ColorAnimation { duration: 160 } }

                            TextField {
                                id: portField
                                anchors.fill: parent
                                anchors.leftMargin: 11
                                anchors.rightMargin: 11
                                background: Item {}
                                placeholderText: "25565"
                                placeholderTextColor: theme.text3
                                color: theme.text1
                                font.pixelSize: 12
                                inputMethodHints: Qt.ImhDigitsOnly
                                validator: IntValidator { bottom: 1; top: 65535 }
                                verticalAlignment: TextInput.AlignVCenter
                                text: page.portText
                                onTextChanged: {
                                    page.portText = text;
                                    page.commitPort();
                                }
                            }
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 6

                        Text {
                            text: bridge.tunnelBackend === "lan"
                                  ? "房主地址（加入房间时填写，如 192.168.0.106:25565）"
                                  : "对端节点（可选，逗号分隔）"
                            font.pixelSize: 11
                            color: theme.text3
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 34
                            radius: 9
                            color: theme.surfaceAlt
                            border.width: 1
                            border.color: peersField.activeFocus ? theme.accent : "transparent"

                            Behavior on border.color { ColorAnimation { duration: 160 } }

                            TextField {
                                id: peersField
                                anchors.fill: parent
                                anchors.leftMargin: 11
                                anchors.rightMargin: 11
                                background: Item {}
                                placeholderText: "1.2.3.4:48879, 5.6.7.8:48879"
                                placeholderTextColor: theme.text3
                                color: theme.text1
                                font.pixelSize: 12
                                verticalAlignment: TextInput.AlignVCenter
                                onTextChanged: page.peers = text
                            }
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    // 创建房间：我是房主（局域网直连时生成本机地址）
                    SproutButton {
                        objectName: "createRoomBtn"
                        text: "创建房间"
                        primary: true
                        active: (bridge.tunnelBackend === "lan" || page.room.trim().length > 0)
                                && !bridge.tunnelRunning
                        implicitHeight: 34
                        fontSize: 12
                        onClicked: {
                            page.commitPort();
                            bridge.startTunnel(page.room.trim(), page.secret, page.peers,
                                               parseInt(page.portText, 10) || 25565,
                                               bridge.tunnelBackend, "host");
                        }
                    }

                    // 加入房间：我是成员（局域网直连时把房主地址填到「对端节点」）
                    SproutButton {
                        objectName: "joinRoomBtn"
                        text: "加入房间"
                        primary: false
                        active: (bridge.tunnelBackend === "lan" || page.room.trim().length > 0)
                                && !bridge.tunnelRunning
                        implicitHeight: 34
                        fontSize: 12
                        onClicked: {
                            page.commitPort();
                            bridge.startTunnel(page.room.trim(), page.secret, page.peers,
                                               parseInt(page.portText, 10) || 25565,
                                               bridge.tunnelBackend, "join");
                        }
                    }

                    SproutButton {
                        text: "打开游戏目录"
                        primary: false
                        active: true
                        implicitHeight: 34
                        fontSize: 12
                        onClicked: bridge.openPath(bridge.mcDir)
                    }

                    Item { Layout.fillWidth: true }

                    Text {
                        Layout.maximumWidth: 330
                        wrapMode: Text.WordWrap
                        text: bridge.tunnelBackend === "lan"
                              ? "提示：房主点「创建房间」拿到 本机地址:端口，成员把该地址填到「对端节点」后点「加入房间」"
                              : "提示：房主点「创建房间」、朋友点「加入房间」，房间名与密钥填一致即可"
                        font.pixelSize: 11
                        color: theme.text3
                    }
                }
            }
        }

        // -------------------------------------------------- 日志
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: 12
            color: theme.card
            border.width: 1
            border.color: theme.border
            clip: true

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 8

                RowLayout {
                    Layout.fillWidth: true

                    Text {
                        text: "联机日志"
                        font.pixelSize: 12
                        font.weight: Font.DemiBold
                        color: theme.text2
                    }

                    Item { Layout.fillWidth: true }

                    Text {
                        text: bridge.tunnelRunning ? "运行中" : "未运行"
                        font.pixelSize: 10
                        color: bridge.tunnelRunning ? theme.accent : theme.text3
                    }
                }

                Flickable {
                    id: logFlick
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    contentWidth: width
                    contentHeight: logText.implicitHeight
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                    Text {
                        id: logText
                        width: logFlick.width
                        wrapMode: Text.WrapAnywhere
                        text: bridge.tunnelLog.length > 0 ? bridge.tunnelLog : "尚无输出"
                        font.family: "Consolas"
                        font.pixelSize: 11
                        color: theme.text3
                        lineHeight: 1.35

                        onTextChanged: logFlick.contentY = Math.max(0, logFlick.contentHeight - logFlick.height)
                    }
                }
            }
        }
    }
}
