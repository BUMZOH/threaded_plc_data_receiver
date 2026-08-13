# Pythonの `except Exception as error` と `except:` の違い

## 1. はじめに

Pythonで例外をまとめて捕捉するとき、次の2つは似ているようで捕捉範囲が異なります。

```python
except Exception as error:
```

```python
except:
```

通常のアプリケーションでは、基本的に `except Exception as error:` を使用します。

---

## 2. 結論

| 書き方 | 捕捉範囲 | 通常のアプリでの推奨 |
|---|---|---|
| `except Exception as error:` | `Exception` を継承した通常の例外 | 推奨 |
| `except:` | `BaseException` 以下を非常に広く捕捉 | 原則として避ける |

一言で覚えるなら、

> **`except Exception` = 通常のエラーをまとめて捕まえる。**  
> **`except:` = それより広すぎるので、特別な理由がなければ使わない。**

---

## 3. Pythonの例外には階層がある

違いを理解するポイントは、Pythonの例外が階層構造になっていることです。

概略は次のようになります。

```text
BaseException
│
├─ SystemExit
├─ KeyboardInterrupt
├─ GeneratorExit
│
└─ Exception
    │
    ├─ AttributeError
    ├─ ValueError
    ├─ RuntimeError
    ├─ TypeError
    ├─ OSError
    │   └─ ConnectionError
    ├─ KeyError
    ├─ IndexError
    └─ その他、多くの通常の例外
```

最上位が `BaseException` で、その下に通常のアプリケーションエラーをまとめる `Exception` があります。

---

## 4. `except Exception as error:` の意味

例えば、

```python
try:
    result = 10 / 0

except Exception as error:
    print(f"エラー: {error}")
```

では `ZeroDivisionError` が発生します。

`ZeroDivisionError` は `Exception` の仲間なので、`except Exception` で捕捉できます。

また、

```python
as error
```

によって発生した例外オブジェクトを `error` という変数で受け取れます。

そのため、

```python
print(error)
```

で具体的なエラー内容を表示できます。

今回の設備データ受信アプリで発生した、

```text
AttributeError:
module 'common_lib_mw.kv_com' has no attribute 'read_devices_l'
```

も `Exception` の仲間なので、次のコードで捕捉できます。

```python
except Exception as error:
    print(f"受信処理エラー: {error}")
```

---

## 5. `except:` の意味

例外クラスを指定せず、

```python
try:
    # 処理

except:
    print("エラーが発生しました")
```

と書くこともできます。

これは「裸のexcept（bare except）」と呼ばれることがあります。

`except:` は `except Exception:` より捕捉範囲が広く、`KeyboardInterrupt` や `SystemExit` なども含めて捕捉します。

---

## 6. `KeyboardInterrupt` まで捕まえてしまう

`KeyboardInterrupt` は、例えばコンソールで実行中のPythonプログラムに `Ctrl + C` を入力して中断するときに発生します。

通常は、

```text
Ctrl + C
    ↓
KeyboardInterrupt
    ↓
プログラムを中断
```

となります。

しかし裸の `except:` は、このような中断のための例外まで捕捉します。

つまり、

> ユーザーがプログラムを止めようとしているのに、その停止要求まで通常のエラーのように捕まえてしまう

可能性があります。

---

## 7. `SystemExit` まで捕まえてしまう

Pythonでは `sys.exit()` などによってプログラムを終了するとき、内部的に `SystemExit` が使われます。

`SystemExit` は `Exception` の子ではなく、`BaseException` の直下にあります。

そのため、

```python
except Exception:
```

では通常捕捉されません。

一方、

```python
except:
```

では捕捉されます。

不用意に裸の `except:` を使用すると、本来終了するはずの処理まで捕捉してしまう可能性があります。

---

## 8. なぜ終了・中断系は `Exception` の外にあるのか

例えば、

```text
ValueError
AttributeError
RuntimeError
ConnectionError
```

などは、「プログラムの処理中に発生した問題」として扱いたい例外です。

一方、

```text
KeyboardInterrupt
SystemExit
```

などは、通常の処理エラーというより「プログラムを中断・終了させるための特別な仕組み」という性格があります。

そのため、概念的には次のように分けられています。

```text
通常のエラー
    ↓
Exception

終了・中断などの特別な例外
    ↓
BaseException直下
```

これによって、

```python
except Exception:
```

と書けば、

> 通常のエラーは広く捕捉するが、終了・中断の仕組みには不用意に干渉しない

という扱いができます。

---

## 9. `if / elif / else` のイメージ

例外処理と条件分岐は別の仕組みですが、捕捉順序は次のように考えると分かりやすいです。

```python
try:
    processing()

except ConnectionError as error:
    print(f"通信エラー: {error}")

except ValueError as error:
    print(f"データエラー: {error}")

except Exception as error:
    print(f"予期しないエラー: {error}")
```

イメージとしては、

```text
ConnectionError？
    ├─ YES → 通信エラー処理
    └─ NO
         ↓
ValueError？
    ├─ YES → データエラー処理
    └─ NO
         ↓
その他のException？
    └─ YES → 予期しないエラー処理
```

となります。

この意味では `except Exception as error:` を、

> **通常の例外に対する最後の受け皿**

と考えると分かりやすいです。

---

## 10. 今回の設備データ受信アプリの場合

今回の `_receive_and_save()` では、サブスレッド内で発生した通常の例外をまとめて見えるようにする方針なので、

```python
try:
    # データ受信
    # JavaScriptへPush
    # データ保存
    # PLCへ完了通知

except Exception as error:
    print(
        f"[{current_time()}] "
        f"{config.name}: 受信処理エラー: {error}"
    )

finally:
    with self.state_lock:
        self.is_receiving[config.name] = False
```

という構成がシンプルです。

これによって、例えば次のような通常の例外を広く捕捉できます。

```text
AttributeError
ValueError
RuntimeError
ConnectionError
OSError
TypeError
KeyError
IndexError
...
```

今回の目的であれば、裸の `except:` まで捕捉範囲を広げる必要はありません。

---

## 11. `except Exception` でも厳密には「すべて」ではない

`except Exception:` を「すべての例外を捕捉する」と表現することがありますが、厳密には違います。

例えば、

```text
KeyboardInterrupt
SystemExit
GeneratorExit
```

などは `Exception` の外側にあるため捕捉されません。

したがって、

> **通常のアプリケーションエラーの大部分を包括的に捕捉する**

という理解がより正確です。

---

## 12. `except BaseException` という書き方

技術的には、

```python
except BaseException as error:
```

と書くこともできます。

これは裸の、

```python
except:
```

に近い非常に広い範囲を明示的に捕捉します。

しかし通常のアプリケーションコードでは、これも基本的には使いません。

多くの場合、

```python
except Exception as error:
```

で十分です。

---

## 13. 使い分け

### 特定の例外だけ捕捉する

```python
except ValueError as error:
```

### 複数の特定例外を同じ処理にする

```python
except (
    ConnectionError,
    OSError,
    RuntimeError,
    ValueError,
) as error:
```

### 通常の例外をまとめて捕捉する

```python
except Exception as error:
```

今回の設備データ受信アプリでは、まずこの方式でサブスレッド内のエラーを見えるようにします。

### 裸の `except:`

```python
except:
```

終了・中断系まで含めて非常に広く捕捉するため、通常は避けます。

---

## 14. 覚え方

```text
except ValueError:
    ↓
ValueErrorだけ


except (ValueError, RuntimeError):
    ↓
指定した複数の例外


except Exception as error:
    ↓
通常の例外をまとめて捕捉
    ★ 普通はこちら


except:
    ↓
終了・中断系まで含めて非常に広く捕捉
    ★ 原則として避ける
```

---

## 15. まとめ

### `except Exception as error:`

- 通常のプログラムで発生する大部分の例外を捕捉する
- `AttributeError`、`ValueError`、`RuntimeError`、`TypeError` などを捕捉できる
- `KeyboardInterrupt` や `SystemExit` などは通常捕捉しない
- `error` から具体的な例外内容を取得できる
- 通常のアプリケーションではこちらを推奨する

### `except:`

- `Exception` より広い範囲を捕捉する
- `KeyboardInterrupt` や `SystemExit` などまで捕捉する
- プログラムの正常な終了・中断を妨げる原因になり得る
- 通常のアプリケーションでは原則として避ける

今回の設備データ受信アプリでは、

```python
except Exception as error:
    print(
        f"[{current_time()}] "
        f"{config.name}: 受信処理エラー: {error}"
    )
```

とすることで、

> **サブスレッド内で発生する通常の例外を広く捕捉しながら、Pythonの終了・中断に関係する特別な例外までは不用意に捕捉しない**

というバランスのよい例外処理にできます。
