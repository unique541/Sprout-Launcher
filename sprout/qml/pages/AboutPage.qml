import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

Item {
    id: page

    readonly property var info: bridge.updateInfo
    readonly property bool hasUpdate: !!info && info.newer === true

    function noteText() {
        var n = info && info.notes ? String(info.notes) : "";
        return n.length > 0 ? n : "暂无更新说明";
    }

    Flickable {
        id: flick
        anchors.fill: parent
        anchors.leftMargin: 26
        anchors.rightMargin: 22
        anchors.topMargin: 4
        anchors.bottomMargin: 4
        contentWidth: width
        contentHeight: col.implicitHeight + 16
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

        ColumnLayout {
            id: col
            width: flick.width
            spacing: 14

            // --------------------------------------------- 应用信息
            Card {
                Layout.fillWidth: true
                Layout.preferredHeight: 132
                corner: 14
                interactive: false

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 20
                    spacing: 18

                    Rectangle {
                        Layout.preferredWidth: 56
                        Layout.preferredHeight: 56
                        radius: 16
                        color: theme.accentSoft

                        Text {
                            anchors.centerIn: parent
                            text: "S"
                            font.pixelSize: 26
                            font.weight: Font.DemiBold
                            color: theme.accent
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 5

                        Text {
                            text: "Sprout 新芽启动器"
                            font.pixelSize: 17
                            font.weight: Font.DemiBold
                            color: theme.text1
                        }

                        Text {
                            text: "版本 " + bridge.appVersion + " · 轻量 Minecraft 启动与管理工具"
                            font.pixelSize: 11
                            color: theme.text3
                        }

                        Text {
                            text: "更新仓库：" + (bridge.updateRepo.length > 0 ? bridge.updateRepo : "未配置（在设置中填写 用户名/仓库名）")
                            font.pixelSize: 11
                            color: theme.text3
                        }
                    }

                    SproutButton {
                        text: "检查更新"
                        primary: true
                        active: bridge.updateRepo.length > 0 && !bridge.busy
                        implicitHeight: 36
                        fontSize: 12
                        onClicked: bridge.checkUpdate()
                    }
                }
            }

            // --------------------------------------------- 更新状态
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: visible ? 124 : 0
                visible: !!info && Object.keys(info).length > 0
                radius: 14
                color: theme.card
                border.width: 1
                border.color: page.hasUpdate ? theme.accent : theme.border

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 18
                    spacing: 10

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10

                        Text {
                            text: page.hasUpdate
                                  ? ("发现新版本 " + info.version)
                                  : ("已是最新版本（" + (info.current || bridge.appVersion) + "）")
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                            color: theme.text1
                        }

                        Rectangle {
                            Layout.preferredHeight: 20
                            Layout.preferredWidth: assetText.implicitWidth + 16
                            radius: 10
                            color: theme.surfaceAlt
                            visible: !!info && !!info.asset_name

                            Text {
                                id: assetText
                                anchors.centerIn: parent
                                text: info && info.asset_name ? info.asset_name : ""
                                font.pixelSize: 10
                                color: theme.text3
                            }
                        }

                        Item { Layout.fillWidth: true }

                        SproutButton {
                            text: "下载更新包"
                            primary: true
                            active: page.hasUpdate && (info.asset_url || "").length > 0 && !bridge.busy
                            implicitHeight: 32
                            fontSize: 12
                            onClicked: bridge.downloadUpdate()
                        }

                        SproutButton {
                            text: "打开发布页"
                            primary: false
                            active: !!info && (info.page || "").length > 0
                            implicitHeight: 32
                            fontSize: 12
                            onClicked: bridge.openUrl(info.page)
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        text: page.noteText()
                        font.pixelSize: 11
                        color: theme.text3
                        wrapMode: Text.WordWrap
                        maximumLineCount: 3
                        elide: Text.ElideRight
                    }
                }
            }

            // --------------------------------------------- 快捷入口
            Card {
                Layout.fillWidth: true
                Layout.preferredHeight: 150
                corner: 14
                interactive: false

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 20
                    spacing: 12

                    Text {
                        text: "快捷入口"
                        font.pixelSize: 13
                        font.weight: Font.DemiBold
                        color: theme.text1
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10

                        SproutButton {
                            text: "游戏目录"
                            primary: false
                            active: true
                            implicitHeight: 34
                            fontSize: 12
                            onClicked: bridge.openPath(bridge.mcDir)
                        }

                        SproutButton {
                            text: "日志目录"
                            primary: false
                            active: true
                            implicitHeight: 34
                            fontSize: 12
                            onClicked: bridge.openPath(bridge.logsPath())
                        }

                        SproutButton {
                            text: "配置目录"
                            primary: false
                            active: true
                            implicitHeight: 34
                            fontSize: 12
                            onClicked: bridge.openPath(bridge.appDataDir())
                        }

                        SproutButton {
                            text: "项目主页"
                            primary: false
                            active: bridge.updateRepo.length > 0
                            implicitHeight: 34
                            fontSize: 12
                            onClicked: bridge.openUrl("https://github.com/" + bridge.updateRepo)
                        }

                        Item { Layout.fillWidth: true }
                    }

                    Text {
                        Layout.fillWidth: true
                        text: "Sprout Launcher 为个人自用的 Minecraft 启动器，游戏资源来自官方与社区镜像，"
                              + "请支持正版并在使用前确认账号与版本匹配。"
                        font.pixelSize: 11
                        color: theme.text3
                        wrapMode: Text.WordWrap
                    }
                }
            }
        }
    }
}
