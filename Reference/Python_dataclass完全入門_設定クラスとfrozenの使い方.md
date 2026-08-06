# Python dataclass完全入門

## ～ `@dataclass(frozen=True)` と設定クラスの設計 ～

## はじめに

Pythonでは、複数の設定値をひとまとめに管理したい場面がよくあります。

今回のコードでは次のように記述されていました。

``` python
@dataclass(frozen=True)
class MotorConfig:
    """モータごとのPLCデバイスと保存先設定。"""

    name: str
    request_device: str
    completion_device: str
    data_start_device: str
    output_directory: Path
```

このクラスは**モータ1台分の設定情報**を管理するための「設定クラス」です。

------------------------------------------------------------------------

# dataclassとは

`@dataclass` はデータを保持するためのクラスを簡単に作る仕組みです。

通常なら `__init__()` を自分で書く必要がありますが、`@dataclass`
を付けるだけで自動生成されます。 さらに `__repr__()` や `__eq__()`
なども自動生成されます。

------------------------------------------------------------------------

# frozen=Trueとは

``` python
@dataclass(frozen=True)
```

の `frozen=True` は

> 作成後に値を変更できない

という意味です。

設定情報が実行中に誤って変更されることを防ぐため、PLC設定などに非常に適しています。

------------------------------------------------------------------------

# MotorConfigとは

`MotorConfig` は「モータ1台分の設定」を表す新しい型です。

Python標準の `int` や `str` と同じように、自分で定義した型になります。

------------------------------------------------------------------------

# 型ヒント

``` python
name: str
request_device: str
completion_device: str
data_start_device: str
output_directory: Path
```

これらは各メンバー変数の型を表します。

`Path` 型を使うことで

``` python
config.output_directory / "sample.csv"
```

のような便利なパス操作ができます。

------------------------------------------------------------------------

# 実際の利用

``` python
config = MotorConfig(
    name="motor1",
    request_device="B10.0",
    completion_device="B20.0",
    data_start_device="EM30000",
    output_directory=Path("motor1"),
)
```

生成後は

``` python
config.name
config.request_device
config.output_directory
```

のように利用できます。

------------------------------------------------------------------------

# この設計のメリット

-   関連する設定を1つにまとめられる
-   コードが読みやすい
-   `__init__()` を書かなくてよい
-   型ヒントが効く
-   `frozen=True` により設定の誤変更を防げる

------------------------------------------------------------------------

# まとめ

`@dataclass(frozen=True)` は、

**「読み取り専用の設定データを安全かつ簡潔に表現するためのPython標準機能」**

です。

PLC設定、通信設定、アプリ設定など、変更されるべきでない情報を表現するときに非常によく使われます。
