# Pythonで文字列から実行する関数を切り替える方法

## 1. はじめに

Pythonでは、関数も「値（オブジェクト）」として扱うことができます。

この性質を利用すると、JSONなどの外部設定ファイルに処理方法の名称を書いておき、その設定値に応じて実行する関数を切り替える設計ができます。

設備データの異常判定では、例えば次のような方式を切り替えたい場合に便利です。

-   単純なしきい値判定
-   統計的手法
-   古典的機械学習
-   Deep Learning

アプリ本体のコードを変更せず、JSONの設定を変更することで判定方式を選択できる構成にできます。

------------------------------------------------------------------------

## 2. 文字列をそのまま関数として実行することはできない

例えば次のコードを考えます。

``` python
def add(a: int, b: int) -> int:
    return a + b


func_name: str = "add"
```

`func_name` には `"add"` という文字列が入っています。

しかし、次のようには実行できません。

``` python
func_name(10, 20)
```

`func_name` の型は `str` であり、関数そのものではないためです。

つまり、

``` python
func_name = "add"
```

は「add関数を変数に格納している」のではなく、単に `"add"`
という文字列を格納しているだけです。

------------------------------------------------------------------------

## 3. Pythonでは関数そのものを変数に格納できる

Pythonでは関数もオブジェクトなので、関数そのものを変数へ代入できます。

``` python
def add(a: int, b: int) -> int:
    return a + b


func = add

result = func(10, 20)

print(result)
```

結果：

``` text
30
```

ここで重要なのは、

``` python
func = add
```

と

``` python
func = add()
```

の違いです。

### `func = add`

``` python
func = add
```

これは **add関数そのものを変数へ代入** しています。

### `func = add()`

``` python
func = add()
```

こちらは **add関数をその場で実行し、その戻り値を変数へ代入** します。

したがって、

``` python
func = add
```

とした場合は、後から

``` python
func(10, 20)
```

のように実行できます。

------------------------------------------------------------------------

## 4. 辞書を使って「文字列」と「関数」を対応させる

外部設定から関数を選択したい場合は、辞書を使う方法が分かりやすく安全です。

``` python
def add(a: int, b: int) -> int:
    return a + b


def sub(a: int, b: int) -> int:
    return a - b


functions = {
    "add": add,
    "sub": sub,
}
```

この辞書は次の対応関係を表しています。

``` text
"add"  -> add関数
"sub"  -> sub関数
```

例えば、

``` python
func_name: str = "add"

result = functions[func_name](10, 20)
```

とすると、

``` python
functions[func_name]
```

によって `add` 関数そのものが取り出されます。

したがって、

``` python
functions[func_name](10, 20)
```

は実質的に、

``` python
add(10, 20)
```

と同じ意味になります。

------------------------------------------------------------------------

## 5. JSONファイルから実行する関数を選択する

今回の目的では、この仕組みをJSON設定ファイルと組み合わせます。

例えば `config.json` に次のように記述します。

``` json
{
    "judge_method": "threshold"
}
```

Python側では、異常判定関数を用意します。

``` python
def judge_threshold(values):
    # しきい値による異常判定
    ...


def judge_statistics(values):
    # 統計的手法による異常判定
    ...


def judge_isolation_forest(values):
    # Isolation Forestによる異常判定
    ...
```

そして、「設定名」と「実際の関数」を辞書で対応させます。

``` python
JUDGE_FUNCTIONS = {
    "threshold": judge_threshold,
    "statistics": judge_statistics,
    "isolation_forest": judge_isolation_forest,
}
```

JSONから読み込んだ設定値が、

``` python
judge_method = "threshold"
```

なら、

``` python
judge_func = JUDGE_FUNCTIONS[judge_method]
```

によって `judge_threshold` 関数そのものを取得できます。

あとは、

``` python
result = judge_func(values)
```

とすれば判定処理を実行できます。

------------------------------------------------------------------------

## 6. 処理の流れ

全体の考え方は次のようになります。

``` text
config.json
    |
    | "judge_method": "threshold"
    v
PythonでJSONを読み込む
    |
    | judge_method = "threshold"
    v
JUDGE_FUNCTIONS
    |
    | "threshold" -> judge_threshold
    | "statistics" -> judge_statistics
    | "isolation_forest" -> judge_isolation_forest
    v
実行する関数を取得
    |
    | judge_func = JUDGE_FUNCTIONS[judge_method]
    v
judge_func(values)
    |
    v
OK / NG 判定
```

------------------------------------------------------------------------

## 7. 設備ごとに判定方法を変えることもできる

この方式の大きな利点は、測定対象ごとに異なる判定方法を設定できることです。

例えばJSONを次のような構成にできます。

``` json
{
    "data_configs": [
        {
            "name": "ToolB_Cross_Torque",
            "judge_method": "threshold"
        },
        {
            "name": "SpindleInverter_MotorCurrent",
            "judge_method": "statistics"
        }
    ]
}
```

すると、

``` text
ToolB_Cross_Torque
    -> threshold
    -> judge_threshold()

SpindleInverter_MotorCurrent
    -> statistics
    -> judge_statistics()
```

というように、測定対象ごとに異常判定アルゴリズムを変更できます。

将来的に、

``` json
"judge_method": "isolation_forest"
```

や

``` json
"judge_method": "autoencoder"
```

などを追加することも可能です。

------------------------------------------------------------------------

## 8. 新しい判定方法を追加するとき

例えばAutoencoderを利用した判定方式を追加するとします。

まず関数を作ります。

``` python
def judge_autoencoder(values):
    ...
```

次に辞書へ登録します。

``` python
JUDGE_FUNCTIONS = {
    "threshold": judge_threshold,
    "statistics": judge_statistics,
    "isolation_forest": judge_isolation_forest,
    "autoencoder": judge_autoencoder,
}
```

JSON側では、

``` json
{
    "judge_method": "autoencoder"
}
```

と指定できます。

この構成なら、判定方式が増えても「どの文字列がどの関数に対応しているのか」が明確です。

------------------------------------------------------------------------

## 9. 存在しない設定値への対策

JSONは人間が編集するため、スペルミスなども考慮する必要があります。

例えば、

``` json
{
    "judge_method": "threshould"
}
```

のような間違いがあると、

``` python
JUDGE_FUNCTIONS[judge_method]
```

では `KeyError` が発生します。

そのため、実際のアプリでは次のように確認すると分かりやすくなります。

``` python
judge_func = JUDGE_FUNCTIONS.get(judge_method)

if judge_func is None:
    raise ValueError(
        f"未対応の異常判定方法です: {judge_method}"
    )

result = judge_func(values)
```

これなら設定ミスが発生した場合にも、

``` text
未対応の異常判定方法です: threshould
```

のように原因を分かりやすくできます。

------------------------------------------------------------------------

## 10. `globals()` や `getattr()` を使う方法について

Pythonには文字列から関数を探す別の方法もあります。

例えば `globals()` などを利用すれば、

``` python
func_name = "add"
func = globals()[func_name]
```

のような処理も可能です。

また、クラスやモジュールでは `getattr()` を利用する方法もあります。

しかし、設定ファイルから処理方法を選択する今回の用途では、最初から実行可能な関数を辞書へ明示的に登録しておく方式の方が適しています。

``` python
JUDGE_FUNCTIONS = {
    "threshold": judge_threshold,
    "statistics": judge_statistics,
}
```

この方式には次の利点があります。

-   実行可能な関数が明確
-   コードを読んだときに対応関係が分かりやすい
-   JSONの値をそのまま無制限に関数検索へ使用しないため安全
-   新しいアルゴリズムを追加しやすい
-   デバッグしやすい

------------------------------------------------------------------------

## 11. ThreadPoolExecutorでも同じ考え方が使われている

「関数そのものを値として扱う」という考え方は、Pythonのさまざまな場所で使われます。

例えば `ThreadPoolExecutor` の、

``` python
executor.submit(
    self._receive_and_save,
    config,
)
```

も同じ考え方です。

ここでは、

``` python
self._receive_and_save
```

に `()` を付けていません。

つまり、その場で関数を実行するのではなく、

> この関数を後でThreadPoolExecutorに実行してもらう

という意味で、関数そのものを `submit()` へ渡しています。

今回の、

``` python
judge_func = JUDGE_FUNCTIONS[judge_method]
```

も基本的には同じ考え方です。

------------------------------------------------------------------------

## 12. 今回の異常検出アプリとの相性

設備異常検出では、データの種類によって最適な判定方式が異なる可能性があります。

例えば、

``` text
モータ電流値
    -> 統計的判定

サーボモータトルク値
    -> しきい値判定

機械振動
    -> 機械学習

将来の複雑な波形判定
    -> Deep Learning
```

のような構成も考えられます。

判定方法をPythonコードの `if / elif` で大量に分岐するのではなく、

``` text
JSON
  ↓
判定方法の名称
  ↓
JUDGE_FUNCTIONS
  ↓
実際の判定関数
```

という構成にすると、設定と処理をきれいに分離できます。

------------------------------------------------------------------------

## 13. まとめ

今回覚えておきたい最重要ポイントは、

> **Pythonでは関数もオブジェクトであり、変数や辞書に格納できる**

ということです。

文字列 `"add"` は関数ではないため、そのまま実行することはできません。

しかし、

``` python
FUNCTIONS = {
    "add": add,
}
```

のように文字列と関数を対応付ければ、

``` python
func_name = "add"
func = FUNCTIONS[func_name]
result = func(10, 20)
```

と実行できます。

設備異常検出アプリでは、

``` text
config.json
    ↓
judge_method
    ↓
JUDGE_FUNCTIONS
    ↓
judge_threshold()
judge_statistics()
judge_isolation_forest()
judge_autoencoder()
```

という構成にすることで、判定アルゴリズムを外部設定から柔軟に切り替えられます。

これは単なる「文字列から関数を呼び出すテクニック」ではなく、

**処理方法を設定から選択可能にする、拡張性の高い設計**

として利用できます。
