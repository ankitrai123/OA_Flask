(function () {
  async function getJSON(url) {
    const res = await fetch(url);
    const data = await res.json().catch(() => null);
    if (!res.ok) throw new Error((data && data.error) || `${url} -> ${res.status}`);
    return data;
  }

  async function postJSON(url, body) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) throw new Error((data && data.error) || `${url} -> ${res.status}`);
    return data;
  }

  window.Api = { getJSON, postJSON };
})();
