import React, { useState, useCallback } from 'react';
import './App.css';

function App() {
  const [dataFile, setDataFile] = useState(null);
  const [jsonFile, setJsonFile] = useState(null);
  const [tsCode, setTsCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [fileInfo, setFileInfo] = useState(null);
  const [tokensUsed, setTokensUsed] = useState(0);
  const [showResult, setShowResult] = useState(false);
  const [copied, setCopied] = useState(false);
  const [execResult, setExecResult] = useState(null);
  const [execError, setExecError] = useState('');
  const [csvBase64, setCsvBase64] = useState(null);

  const handleDrop = useCallback((e, setter) => {
    e.preventDefault();
    e.stopPropagation();
    const file = e.dataTransfer.files[0];
    if (file) setter(file);
  }, []);

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleFileSelect = (e, setter) => {
    const file = e.target.files[0];
    if (file) setter(file);
  };

  const getFileExtension = (filename) => {
    return filename.split('.').pop().toUpperCase();
  };

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + ' Б';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' КБ';
    return (bytes / (1024 * 1024)).toFixed(1) + ' МБ';
  };

  const handleGenerate = async () => {
    if (!dataFile) {
      setError('Загрузите файл с данными');
      return;
    }

    setLoading(true);
    setError('');
    setTsCode('');

    try {
      const formData = new FormData();
      formData.append('file', dataFile);

      if (jsonFile) {
        const jsonText = await jsonFile.text();
        formData.append('target_json', jsonText);
      }

      const apiUrl = window.location.hostname === 'localhost' ? 'http://localhost:8000/generate' : '/generate';
      const response = await fetch(apiUrl, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || 'Ошибка сервера');
      }

      const data = await response.json();
      setTsCode(data.typescript_code);
      setFileInfo(data.file_info);
      setTokensUsed(data.tokens_used);
      setCsvBase64(data.csv_base64 || null);
      setShowResult(true);
    } catch (err) {
      setError(err.message || 'Не удалось подключиться к серверу');
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(tsCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const stripTypes = (code) => {
    let js = code;
    // 1. Убираем interface/type блоки
    js = js.replace(/(?:export\s+)?(?:interface|type)\s+\w+\s*=?\s*\{[^}]*\};?/gs, '');
    // 2. Убираем export default
    js = js.replace(/export\s+default\s+/g, '');
    // 3. Убираем return type функции: ): { ... }[] { → ) {  и  ): Type[] { → ) {
    js = js.replace(/\)\s*:\s*\{[^}]*\}(?:\[\])?\s*\{/g, ') {');
    js = js.replace(/\)\s*:\s*[A-Za-z][\w.<>,\s|]*(?:\[\])?\s*\{/g, ') {');
    // 4. Убираем типы параметров: (param: string, param2: number)
    js = js.replace(/(\(|,\s*)(\w+)\s*:\s*(?:string|number|boolean|any|void|never|unknown)(?:\[\])?\s*(?=[,)])/g, '$1$2');
    js = js.replace(/(\(|,\s*)(\w+)\s*:\s*(?:Record|Map|Set|Array|Promise)<[^>]*>\s*(?=[,)])/g, '$1$2');
    // 5. Убираем типы переменных: const x: Type = → const x =
    js = js.replace(/(const|let|var)\s+(\w+)\s*:\s*(?:Record|Map|Set|Array|Promise)<[^>]*>\s*=/g, '$1 $2 =');
    js = js.replace(/(const|let|var)\s+(\w+)\s*:\s*[A-Za-z][\w]*(?:\[\])?\s*=/g, '$1 $2 =');
    // 6. Убираем as Type
    js = js.replace(/\s+as\s+\w+(?:\[\])?/g, '');
    // 7. Убираем дженерики у вызовов: fn<Type>( → fn(
    js = js.replace(/(\w)\s*<\s*\w+(?:\[\])?\s*>\s*\(/g, '$1(');
    return js;
  };

  const handleExecute = async () => {
    if (!dataFile || !tsCode) return;
    setExecError('');
    setExecResult(null);
    try {
      let base64;
      if (csvBase64) {
        // Для бинарных форматов используем CSV от сервера
        base64 = csvBase64;
      } else {
        base64 = await new Promise((resolve) => {
          const reader = new FileReader();
          reader.onload = () => resolve(reader.result.split(',')[1]);
          reader.readAsDataURL(dataFile);
        });
      }
      let jsCode = stripTypes(tsCode);
      // Заменяем atob на UTF-8 безопасный декодер
      const utf8Helper = 'function _u8d(b){var d=atob(b),u=new Uint8Array(d.length);for(var i=0;i<d.length;i++)u[i]=d.charCodeAt(i);return new TextDecoder("utf-8").decode(u);}\n';
      jsCode = utf8Helper + jsCode.replace(/\batob\s*\(/g, '_u8d(');
      // eslint-disable-next-line no-new-func
      const fn = new Function('base64File', jsCode + '\nreturn parseFile(base64File);');
      const result = fn(base64);
      // Если результат — Promise, ждём его
      const finalResult = result instanceof Promise ? await result : result;
      setExecResult(finalResult);
    } catch (err) {
      setExecError('Ошибка выполнения: ' + err.message);
    }
  };

  const handleDownload = () => {
    const blob = new Blob([tsCode], { type: 'text/typescript' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'converter.ts';
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleBack = () => {
    setShowResult(false);
    setTsCode('');
    setFileInfo(null);
    setTokensUsed(0);
    setDataFile(null);
    setJsonFile(null);
    setCsvBase64(null);
    setExecResult(null);
    setExecError('');
  };

  if (showResult) {
    return (
      <div className="app">
        <div className="container">
          <h1 className="title">Ваши файлы</h1>
          <p className="subtitle">TypeScript-функция для парсинга загруженного файла</p>

          {fileInfo && (
            <div className="file-info-card">
              <div className="file-info-left">
                <div className="file-icon">&#128196;</div>
                <div>
                  <div className="file-label">ФАЙЛ С ДАННЫМИ</div>
                  <div className="file-name">{fileInfo.filename}</div>
                  {dataFile && <div className="file-size">{formatFileSize(dataFile.size)}</div>}
                </div>
              </div>
              <span className="file-badge">{getFileExtension(fileInfo.filename)}</span>
            </div>
          )}

          <div className="code-section">
            <div className="code-header">
              <span>Сгенерированный TypeScript-код</span>
              <button className="copy-btn" onClick={handleCopy}>
                {copied ? 'Скопировано' : 'Копировать'}
              </button>
            </div>
            <pre className="code-block">
              <code>{tsCode}</code>
            </pre>
          </div>

          {tokensUsed > 0 && (
            <div className="tokens-info">
              Использовано токенов: ~{tokensUsed}
            </div>
          )}

          <button className="execute-btn" onClick={handleExecute}>
            Выполнить код
          </button>

          {execError && <div className="error-msg">{execError}</div>}

          {execResult && (
            <div className="code-section">
              <div className="code-header">
                <span>Результат выполнения (JSON)</span>
              </div>
              <pre className="code-block result-block">
                <code>{JSON.stringify(execResult, null, 2)}</code>
              </pre>
            </div>
          )}

          <button className="download-btn" onClick={handleDownload}>
            Скачать .ts файл
          </button>

          <button className="back-btn" onClick={handleBack}>
            Назад
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="app">
      <div className="container">
        <h1 className="title">Загрузите файлы</h1>
        <p className="subtitle">Файл с данными и пример JSON — сгенерируем TypeScript-код</p>

        <div
          className={`drop-zone ${dataFile ? 'has-file' : ''}`}
          onDrop={(e) => handleDrop(e, setDataFile)}
          onDragOver={handleDragOver}
          onClick={() => document.getElementById('dataFileInput').click()}
        >
          <input
            id="dataFileInput"
            type="file"
            hidden
            accept=".csv,.xls,.xlsx,.json,.xml,.pdf,.docx,.html,.htm,.png,.jpg,.jpeg"
            onChange={(e) => handleFileSelect(e, setDataFile)}
          />
          <div className="drop-icon">&#8679;</div>
          <div className="drop-title">Файл 1</div>
          <div className="drop-desc">файл с табличными данными (csv, xls, pdf...)</div>
          {dataFile ? (
            <div className="file-selected">
              {dataFile.name} ({formatFileSize(dataFile.size)})
            </div>
          ) : (
            <div className="drop-hint">перетащите или нажмите</div>
          )}
        </div>

        <div className="separator">
          <span className="separator-icon">+</span>
        </div>

        <div
          className={`drop-zone ${jsonFile ? 'has-file' : ''}`}
          onDrop={(e) => handleDrop(e, setJsonFile)}
          onDragOver={handleDragOver}
          onClick={() => document.getElementById('jsonFileInput').click()}
        >
          <input
            id="jsonFileInput"
            type="file"
            hidden
            accept=".json"
            onChange={(e) => handleFileSelect(e, setJsonFile)}
          />
          <div className="drop-icon">&#8679;</div>
          <div className="drop-title">Файл 2</div>
          <div className="drop-desc">пример JSON — как должны выглядеть данные (опционально)</div>
          {jsonFile ? (
            <div className="file-selected">
              {jsonFile.name} ({formatFileSize(jsonFile.size)})
            </div>
          ) : (
            <div className="drop-hint">перетащите или нажмите</div>
          )}
        </div>

        {error && <div className="error-msg">{error}</div>}

        <button
          className="generate-btn"
          onClick={handleGenerate}
          disabled={loading || !dataFile}
        >
          {loading ? 'Генерация...' : 'Загрузите файлы'}
        </button>
      </div>
    </div>
  );
}

export default App;
