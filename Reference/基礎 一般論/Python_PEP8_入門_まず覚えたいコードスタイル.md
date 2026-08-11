# Python コードスタイル入門 ― まず覚えたい PEP 8 の基本

## 1. PEP 8とは

Pythonには、コードを読みやすく統一するための代表的なスタイルガイド **PEP
8** があります。

PEPは **Python Enhancement Proposal**
の略で、Pythonに関する仕様・設計・運用上の提案をまとめた文書です。その中でPEP
8は、Pythonコードの「見た目・書き方」の基本を扱っています。

PEP 8はPythonの文法そのものではありません。

``` python
x=10
```

でも実行できますが、通常は次のように書きます。

``` python
x = 10
```

つまり、

-   **文法**：Pythonとして実行できるか
-   **PEP 8**：人間が読みやすく、統一されたコードになっているか

という違いがあります。

特に長期間メンテナンスするアプリでは、「数か月後の自分が読んでも分かるコード」にするために非常に役立ちます。

------------------------------------------------------------------------

## 2. 最初から全部覚える必要はない

PEP
8には細かな規則がたくさんあります。最初から全文を暗記する必要はありません。

まずは次の10項目を優先して覚えるのがおすすめです。

1.  インデントはスペース4個
2.  変数名・関数名は `snake_case`
3.  クラス名は `PascalCase`
4.  定数は `UPPER_CASE`
5.  演算子の前後には基本的にスペース
6.  カンマの後ろにはスペース
7.  関数・クラスの間には適切な空行
8.  importはファイル上部に整理
9.  1行を長くしすぎない
10. コメントやdocstringで目的・理由を分かりやすくする

この10項目だけでも、Pythonコードはかなり整います。

------------------------------------------------------------------------

# 3. インデントはスペース4個

Pythonではインデントが見た目だけではなく、**プログラムの構造そのもの**を表します。

``` python
if is_running:
    print("実行中です")
```

関数でも同じです。

``` python
def start_motor():
    print("モータを起動します")
```

さらに内側へ入る場合は4個ずつ増えます。

``` python
if is_running:
    if has_error:
        print("異常が発生しています")
```

PEP 8ではタブよりスペースを推奨しています。VS
CodeではTabキーを押してもスペース4個として入力する設定が一般的なので、普段はエディタに任せれば大丈夫です。

------------------------------------------------------------------------

# 4. 変数名は snake_case

Pythonの変数名は基本的に **小文字 + アンダースコア** です。

``` python
motor_current = 100
machine_no = 3
inspection_start_time = "08:00"
```

これを **snake_case（スネークケース）** と呼びます。

次のような名前よりPythonらしい書き方です。

``` python
motorCurrent = 100
MachineNo = 3
inspectionstarttime = "08:00"
```

JavaScriptでは `camelCase` が一般的ですが、Pythonでは変数・関数に
`snake_case` を使うのが基本です。

------------------------------------------------------------------------

# 5. 関数名も snake_case

``` python
def read_motor_current():
    pass


def save_to_database():
    pass


def get_inspection_start_time():
    pass
```

関数は処理を表すので、`get`、`read`、`save`、`create`、`update`、`delete`、`check`
などの動詞を使うと意味が分かりやすくなります。

``` python
def data():
    pass
```

より、

``` python
def read_plc_data():
    pass
```

の方が目的が明確です。

------------------------------------------------------------------------

# 6. クラス名は PascalCase

クラス名は各単語の先頭を大文字にします。

``` python
class MotorReceiver:
    pass


class PlcConnection:
    pass


class InspectionResult:
    pass
```

これを **PascalCase（パスカルケース）** と呼びます。

  種類     書き方       例
  -------- ------------ ------------------------
  変数     snake_case   `motor_current`
  関数     snake_case   `read_motor_current()`
  クラス   PascalCase   `MotorReceiver`
  定数     UPPER_CASE   `PLC_IP_ADDRESS`

この4種類は最初に覚えておく価値があります。

------------------------------------------------------------------------

# 7. 定数は UPPER_CASE

プログラム実行中に基本的に変更しない設定値は、大文字とアンダースコアで表します。

``` python
PLC_IP_ADDRESS = "192.168.0.10"
POLLING_INTERVAL = 0.1
MAX_WORKERS = 3
BASE_DIRECTORY = "data"
```

Pythonには「絶対に変更できない定数」の専用文法はありません。

`UPPER_CASE` は、

> この値は基本的に変更せず定数として扱います

という人間への意思表示です。

------------------------------------------------------------------------

# 8. 演算子の前後にはスペース

基本的には演算子の左右にスペースを入れます。

``` python
count = 10
total = count + 5
is_ready = count > 0
```

比較演算子も同様です。

``` python
if count == 10:
    pass

if temperature >= 100:
    pass
```

論理演算子も読みやすく空けます。

``` python
if is_running and not has_error:
    pass
```

次のように詰めると読みにくくなります。

``` python
count=10
total=count+5
```

------------------------------------------------------------------------

# 9. カンマの後ろにはスペース

``` python
values = [10, 20, 30]
print(name, value, status)
```

関数の引数も同様です。

``` python
def connect(ip_address, port, timeout):
    pass
```

基本は、

> カンマの前には空けない。カンマの後ろに1スペース。

です。

------------------------------------------------------------------------

# 10. 関数のデフォルト引数では `=` の周囲を空けない

普通の代入では、

``` python
timeout = 5
```

ですが、デフォルト引数やキーワード引数では、

``` python
def connect(timeout=5):
    pass

connect(timeout=5)
```

と書きます。

ただし型アノテーションとデフォルト値を組み合わせる場合は、

``` python
def connect(timeout: float = 5.0) -> None:
    pass
```

となります。

最初は「通常の代入と関数の引数では少し違う」と覚えておけば十分です。

------------------------------------------------------------------------

# 11. コロンの前にはスペースを入れない

``` python
if is_running:
    pass

for value in values:
    print(value)
```

次のようには通常書きません。

``` python
if is_running :
    pass
```

辞書でも同じです。

``` python
motor = {
    "name": "motor1",
    "current": 120,
}
```

------------------------------------------------------------------------

# 12. 空行でコードのまとまりを見せる

トップレベルの関数やクラスの定義間は、PEP 8では基本的に **空行2行**
です。

``` python
def read_data():
    pass


def save_data():
    pass


class MotorReceiver:
    pass
```

クラス内部のメソッド間は通常 **空行1行** です。

``` python
class MotorReceiver:
    def start(self):
        pass

    def stop(self):
        pass
```

空行の数を数えること自体が目的ではありません。**処理のまとまりを人間が一目で認識できること**が大切です。

------------------------------------------------------------------------

# 13. importはファイル上部へまとめる

基本的にimport文はファイルの上部に書きます。

一般的には次の順序でグループ分けします。

1.  Python標準ライブラリ
2.  外部ライブラリ
3.  自分のプロジェクト内モジュール

``` python
import csv
import threading
from pathlib import Path

import pandas as pd
import webview

import kv_com
```

各グループの間を空行で区切ると、「標準なのか」「pipで入れたものなのか」「自作なのか」が分かりやすくなります。

------------------------------------------------------------------------

# 14. 原則として1行に1つのimport

``` python
import csv, threading, time
```

より、

``` python
import csv
import threading
import time
```

が基本です。

一方、`from ... import ...` では複数名を書く場合があります。

``` python
from concurrent.futures import Future, ThreadPoolExecutor
```

長い場合は、

``` python
from concurrent.futures import (
    Future,
    ThreadPoolExecutor,
    as_completed,
)
```

のように書けます。

------------------------------------------------------------------------

# 15. 1行を長くしすぎない

PEP 8では伝統的に、通常のコードについて **1行79文字以内**
が推奨されています。

ただし現在の実務ではBlackなどのフォーマッタで88文字を基準にするプロジェクトもあります。

重要なのは、**横に長すぎて読みにくいコードを作らないこと**です。

``` python
result = read_motor_current(
    plc_ip_address,
    start_device,
    data_count,
    timeout,
    retry_count,
)
```

Pythonでは、括弧の中で自然に改行する書き方が非常によく使われます。

------------------------------------------------------------------------

# 16. 長い関数呼び出しは括弧の中で改行

例えば、

``` python
self.executor = ThreadPoolExecutor(
    max_workers=len(MOTOR_CONFIGS),
    thread_name_prefix="motor-receiver",
)
```

は非常にPythonらしい書き方です。

一行に詰めるより、

-   引数を見つけやすい
-   後から追加しやすい
-   Gitの差分を確認しやすい

というメリットがあります。

------------------------------------------------------------------------

# 17. 複数行では末尾カンマが便利

``` python
thread = threading.Thread(
    target=self._receive_and_save,
    args=(config,),
    name=f"{config.name}-receiver",
    daemon=True,
)
```

最後の `daemon=True,` にもカンマがあります。

複数行の引数・リスト・タプルでは、最後にもカンマを付けるスタイルがよく使われます。

``` python
MOTOR_NAMES = (
    "motor1",
    "motor2",
    "motor3",
)
```

後から要素を追加しやすく、Gitの差分もきれいになります。

------------------------------------------------------------------------

# 18. 1行に複数処理を詰め込まない

``` python
x = 10; y = 20; print(x + y)
```

より、

``` python
x = 10
y = 20
print(x + y)
```

が読みやすいです。

また、

``` python
if is_ready: start()
```

より、

``` python
if is_ready:
    start()
```

を基本にします。

------------------------------------------------------------------------

# 19. Boolean値との比較はシンプルに

``` python
if is_running == True:
    pass
```

より、

``` python
if is_running:
    pass
```

と書きます。

Falseの場合も、

``` python
if not is_running:
    pass
```

が自然です。

Boolean変数に `is_`、`has_`、`can_`、`should_`
などを使うとさらに読みやすくなります。

``` python
if has_error:
    show_error()

if should_reset_plc:
    reset_plc()
```

------------------------------------------------------------------------

# 20. `None` の比較には `is` / `is not`

``` python
if result is None:
    pass

if result is not None:
    pass
```

次の書き方は避けます。

``` python
if result == None:
    pass
```

`None` は `is None` / `is not None` と覚えておきましょう。

------------------------------------------------------------------------

# 21. コメントはコードをそのまま日本語にしない

例えば、

``` python
# countに1を足す
count += 1
```

では、コードを見れば内容が分かります。

コメントでは「なぜそうするのか」を説明すると価値があります。

``` python
# PLC要求がONのままでも同じ処理を再受付しないようラッチする。
request_latched = True
```

また、`#` の後ろにはスペースを入れます。

``` python
# PLCからデータを読み込む。
```

------------------------------------------------------------------------

# 22. docstringで目的を書く

関数・クラス・モジュールの説明には **docstring** が使えます。

``` python
def read_motor_current():
    """PLCからモータ電流値を読み込む。"""
```

``` python
class MotorReceiver:
    """PLC要求監視とモータ電流データ受信を管理する。"""
```

モジュール全体にも書けます。

``` python
"""PLCからモータ電流値を受信し、SQLiteへ保存する。"""
```

大まかには、

-   `# コメント` → コード中の補足
-   `"""docstring"""` → モジュール・クラス・関数などの目的や仕様

と考えると分かりやすいです。

------------------------------------------------------------------------

# 23. `_name` の意味

先頭のアンダースコアには慣習的な意味があります。

``` python
def _receive_and_save(self):
    pass
```

これは、

> クラスやモジュールの内部で使うことを想定している

という意思表示です。

PythonにはJavaやC#の `private`
と完全に同じ仕組みはないため、名前によって意図を伝える文化があります。

ただし `_`
が付いているから絶対に外部から呼べない、という意味ではありません。

------------------------------------------------------------------------

# 24. 読みやすい名前を優先する

``` python
d = read_data()
```

より、

``` python
motor_current_data = read_data()
```

の方が意味が分かります。

ただし、極端に長い名前も逆に読みにくくなります。

``` python
motor_current_data_received_from_plc_device = read_data()
```

「その場所で意味を推測できる程度」を目安にします。

------------------------------------------------------------------------

# 25. `l`、`O`、`I` の1文字変数には注意

次の名前はフォントによって見分けにくくなります。

``` python
l = 1
O = 0
I = 1
```

PEP
8でも、これらを1文字の変数名として使うことは避けるよう推奨されています。

意味のある名前を付けられる場面では、

``` python
for config in MOTOR_CONFIGS:
    print(config.name)
```

のように具体的にします。

------------------------------------------------------------------------

# 26. 命名規則の早見表

  対象                   基本スタイル       例
  ---------------------- ------------------ ------------------------
  変数                   snake_case         `motor_current`
  関数                   snake_case         `read_motor_current()`
  メソッド               snake_case         `start_monitoring()`
  クラス                 PascalCase         `MotorReceiver`
  定数                   UPPER_CASE         `POLLING_INTERVAL`
  内部用関数・メソッド   `_` + snake_case   `_receive_data()`
  モジュール名           短いsnake_case     `kv_com.py`
  パッケージ名           短い小文字を基本   `utils`

------------------------------------------------------------------------

# 27. 文字列の `'` と `"` はどちらでもよい

Pythonでは、

``` python
name = "motor1"
```

も、

``` python
name = 'motor1'
```

も使えます。

PEP 8はどちらか一方を絶対に使うようには定めていません。

大切なのは **プロジェクト内で一貫させること** です。

------------------------------------------------------------------------

# 28. PEP 8より大切な「一貫性」

PEP 8の目的は、規則を守ること自体ではありません。

目的は、

-   読みやすい
-   理解しやすい
-   修正しやすい
-   間違いを見つけやすい
-   他のPythonコードと似た感覚で読める

コードを作ることです。

既存プロジェクトにPEP
8と少し異なる一貫したルールがある場合、一部分だけ無理に変更すると逆に読みにくくなることがあります。

**PEP 8と同時に、プロジェクト内の一貫性も重要**です。

------------------------------------------------------------------------

# 29. 細かな整形はツールに任せられる

実際の開発では、PEP 8をすべて目視確認する必要はありません。

代表的なツールには次があります。

-   **Black**：コードを自動整形するフォーマッタ
-   **Ruff**：スタイルや潜在的な問題を高速にチェックするリンター
-   **VS Code**：保存時フォーマットや警告表示

役割分担のイメージは、

``` text
人間
  ↓
良い名前・分かりやすい構造・設計を考える
  ↓
Black / Ruff
  ↓
細かな書式を自動整形・チェック
```

です。

人間は「変数名が適切か」「関数をどう分割するか」「設計が分かりやすいか」といった本質的な部分に集中できます。

------------------------------------------------------------------------

# 30. PEP 8と型ヒントは別の話

``` python
def read_data(device: str, count: int) -> list[int]:
    pass
```

この、

``` python
device: str
count: int
-> list[int]
```

は型ヒントです。

型ヒントの中心的なガイドラインは **PEP 484** などで扱われています。

大まかには、

-   **PEP 8** → コードスタイル
-   **PEP 257** → docstring
-   **PEP 484** → 型ヒント

です。

「Pythonの書き方は全部PEP 8」というわけではありません。

------------------------------------------------------------------------

# 31. 実例：読みにくいコードを整える

変更前：

``` python
class motorreceiver:
    def ReadData(self,ip,cnt):
        if cnt==0:
            return None
        d=read(ip,cnt)
        return d
```

基本的なスタイルに合わせると、

``` python
class MotorReceiver:
    def read_data(self, ip_address, count):
        if count == 0:
            return None

        data = read(ip_address, count)
        return data
```

となります。

主な変更点は、

-   `motorreceiver` → `MotorReceiver`
-   `ReadData` → `read_data`
-   `ip` → `ip_address`
-   `cnt` → `count`
-   カンマの後ろにスペース
-   `==` の前後にスペース
-   処理のまとまりに空行
-   `d` → `data`

です。

処理内容はほぼ同じでも、かなり読みやすくなります。

------------------------------------------------------------------------

# 32. PLCアプリ風の例

``` python
from concurrent.futures import ThreadPoolExecutor

import kv_com


PLC_IP_ADDRESS = "192.168.0.10"
POLLING_INTERVAL = 0.1
MAX_WORKERS = 3


class MotorReceiver:
    """PLCからモータ電流データを受信する。"""

    def __init__(self, plc_ip_address: str) -> None:
        self.plc_ip_address = plc_ip_address
        self.executor = ThreadPoolExecutor(
            max_workers=MAX_WORKERS,
            thread_name_prefix="motor-receiver",
        )

    def read_motor_current(
        self,
        start_device: str,
        data_count: int,
    ) -> list[int]:
        """指定デバイスからモータ電流値を読み込む。"""
        return kv_com.read_device(
            self.plc_ip_address,
            start_device,
            data_count,
        )
```

ここでは、

-   定数 → `UPPER_CASE`
-   クラス → `PascalCase`
-   メソッド → `snake_case`
-   変数 → `snake_case`
-   インデント → スペース4個
-   長い引数 → 括弧内で改行
-   複数行の末尾 → カンマ
-   クラス・メソッド → docstring

という基本をまとめて確認できます。

------------------------------------------------------------------------

# 33. 初心者のうちは後回しでよい細則

PEP 8には、

-   二項演算子の細かな改行位置
-   特殊メソッド周辺の規則
-   複雑なimportの扱い
-   public / internal interfaceの細かな命名
-   継承を前提とした命名

など、より細かな内容もあります。

これらは必要になった時点で覚えれば十分です。

最初から細則に気を取られて、プログラムを書くこと自体が難しくなるのは本末転倒です。

------------------------------------------------------------------------

# 34. 最初に身につけたいチェックリスト

Pythonコードを書いたら、まず次を確認してみましょう。

-   [ ] インデントはスペース4個か
-   [ ] 変数名は `snake_case` か
-   [ ] 関数名・メソッド名は `snake_case` か
-   [ ] クラス名は `PascalCase` か
-   [ ] 定数は `UPPER_CASE` か
-   [ ] `=`、`+`、`==` などの前後に適切なスペースがあるか
-   [ ] カンマの後ろにスペースがあるか
-   [ ] `if xxx == True` のような不要な比較をしていないか
-   [ ] `None` は `is None` / `is not None` で比較しているか
-   [ ] importはファイル上部で整理されているか
-   [ ] 1行が極端に長くないか
-   [ ] 長い引数は括弧内で改行しているか
-   [ ] 変数名だけで意味がある程度分かるか
-   [ ] コメントがコードの単なる言い換えになっていないか
-   [ ] 必要な関数・クラスにdocstringがあるか

------------------------------------------------------------------------

# 35. 覚える優先順位

## 最優先

``` text
インデント        → スペース4個
変数・関数        → snake_case
クラス            → PascalCase
定数              → UPPER_CASE
演算子            → 前後にスペース
カンマ            → 後ろにスペース
```

## 次に覚える

``` text
import            → 上部に整理
空行              → 処理のまとまりを分ける
長い行            → 括弧を使って改行
Boolean           → if is_ready:
None              → is None
内部用メソッド    → _method_name
```

## 慣れてから

``` text
Black             → 自動フォーマット
Ruff              → コードチェック
PEP 257           → docstring
PEP 484           → 型ヒント
より細かなPEP 8規則
```

------------------------------------------------------------------------

# 36. まとめ

PEP
8は「Pythonを動かすための文法」ではなく、**Pythonコードを読みやすく統一するためのスタイルガイド**です。

最初に全部を覚える必要はありません。

まずは、

``` python
motor_current = 100


def read_motor_current():
    pass


class MotorReceiver:
    pass


PLC_IP_ADDRESS = "192.168.0.10"
```

という命名規則と、

``` python
if motor_current >= 100:
    print("電流値が高いです")
```

のようなスペース・インデントの感覚を身につければ十分です。

そして将来的には、

> **細かな整形はツールに任せ、人間は読みやすい名前・構造・設計を考える**

という方向がおすすめです。

PEP
8を学ぶ最大の目的は、単に「規則どおりのコード」を書くことではありません。

**未来の自分や他の人が、安心して読んで修正できるPythonコードを書くこと**です。
