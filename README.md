# workou-colab

Google Colab を使ったモデル検証用ノートブックです。

## ph0: Qwen3.8 Flash-Next × Pi

[Colabでノートブックを開く](https://colab.research.google.com/github/workoushr/workou-colab/blob/main/flash_next_ph0.ipynb)

目的は、Qwen3.8 Flash-Next を Colab で起動し、**こちら側で動くPiの implement agent** として使えるかを判断することです。Colab は推論とAPI公開を担当し、`read` / `write` / `edit` / `bash` の実行はPi側のPCで行います。WebアクセスもPi側の `bash` または別途登録したツールで行います。

### 必要なもの

- Google Colab で **A100 80GB + High RAM** を割り当てられるプラン。40GB GPUではモデルが収まりません。割当が保証されるわけではありません。
- Colabランタイムの空きディスク **110GiB以上**、RAM **120GiB以上**。モデルの重みは約100GiBです。
- Piを動かす別のPC。ノートブックのAPIはCloudflareの一時トンネルから到達できます。

ノートブックの最初のセルでGPU、RAM、ディスク容量を確認し、不適合ならダウンロード前に停止します。実行中はColabの利用枠を消費します。検証が終わったら **ランタイム → 接続解除してランタイムを削除** してください。

### 実行手順

1. 上のリンクからColabで開き、ランタイムをA100 / High RAMに設定します。
2. セルを上から実行します。`architectds/collabosm` の固定コミットを取得し、[Pi向けパッチ](patches/pi-tool-calling.patch)のSHA-256を検証して適用します。ランタイムのPython/Torch/CUDAが固定wheelに一致しないときはソースビルドへ切り替わります。
3. モデルの取得とロード後、外部APIでChat応答を確認し、架空ファイルを使った `read` の呼び出し→結果返却→再応答を確認します。このセルはPiの実ファイルを操作しません。
4. 最後に表示される `baseUrl` とAPIキーをPi側へ設定し、**Pi実機で**小さな一時ディレクトリを対象に `read` → `write` → `edit` → `bash` とWebアクセスを試します。ph0の判定は、この実機試験まで含めて行います。

### Pi接続設定

Piを動かすPCの `~/.pi/agent/models.json` に追加します。`baseUrl` はノートブックの最後に表示される値に置き換えてください。

```json
{
  "providers": {
    "collabosm": {
      "baseUrl": "https://<今回のホスト>.trycloudflare.com/v1",
      "api": "openai-completions",
      "apiKey": "$COLLABOSM_API_KEY",
      "compat": {
        "supportsStrictMode": false,
        "supportsDeveloperRole": false,
        "supportsReasoningEffort": false
      },
      "models": [{
        "id": "qwen3.8-flash-next-exl3",
        "name": "Qwen3.8 Flash-Next (Colab ph0)",
        "reasoning": false,
        "input": ["text"],
        "contextWindow": 262144,
        "maxTokens": 8192
      }]
    }
  }
}
```

Piを起動するシェルで `COLLABOSM_API_KEY` を設定し、Piの `/model` から `collabosm` を選びます。**`openai-completions` を指定してください。** このパッチではChat Completionsのfunction toolsに対応しています。Responses APIはテキスト用です。

キーはノートブックの出力に表示されます。APIキー、出力済みノートブック、個人情報や社内データはGitHubにコミットしないでください。検証にはダミーのファイルだけを使ってください。Piの作業内容とツール結果はColab上のモデルに送信されます。

### ph0の判定項目

| 項目 | 合格条件 |
|---|---|
| 起動 | A100 80GB / High RAMでモデルをロードし、トンネル経由で認証付きAPIにアクセスできる |
| Chat | 日本語の短い依頼に空でない返答が届く |
| Tool protocol | `read` の `tool_calls` と結果返却後の再応答が成立する |
| Pi実機 | 一時ディレクトリで `read` / `write` / `edit` / `bash` が使える。WebアクセスもPi側に用意した手段で動く |
| 実用性 | implement agentの小さな課題を完遂し、遅延と誤ったツール引数を記録できる |

ノートブックのAPI試験だけではモデルのコード修正能力や、Piによる実ファイル操作は評価できません。`tool_calls` が返らなければ、その結果を確認してからプロンプトやモデル設定を調整します。

### 固定版と再現性

- 上流: `architectds/collabosm` の `138ea8cd9b8edd030f26d945deae19fad8cf7c6d`
- モデル: `turboderp/Qwen3.8-Flash-Next-exl3` のリビジョン `55a732e0c4c3d4614bc42b68493bb930d9b02c0a`
- Pi向け差分: [`patches/pi-tool-calling.patch`](patches/pi-tool-calling.patch)、SHA-256 `07119dacd7852303714521a99bd653da779626d19be575346aa45c75982c7c96`
- API公開: Bearer認証を伴うCloudflare quick tunnel。URLはランタイム再起動で変わります。

パッチは上流リポジトリの内容を変更するため、この固定コミット以外には自動適用しません。依存ランタイムやColabの提供環境が変わった場合、起動前の確認またはソースビルドで停止・失敗することがあります。
