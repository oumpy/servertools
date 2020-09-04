# Post2Slack

原案・原作 AtamaokaC

## 概要
標準入力をSlackに投稿する。

## 使い方例
コマンド `hoge` の出力をSlackに投稿する。
```bash
$ hoge | post2slack
```

## 設定
Slack Tokenは `~/etc/slack_token` から読み込み。
`-c` オプションでチャンネル指定 (デフォルトは `random`)。
その他詳細は `post2slack -h` を参照。
