const express = require('express');
const { Pool } = require('pg');
const cors = require('cors');
const path = require('path');
const http = require('http');

const app = express();
app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// PostgreSQL
const pool = new Pool({
  host: 'localhost',
  port: 5432,
  database: 'notices',
  user: 'user_EjB5yH',
  password: 'password_QXyMXR',
  max: 20
});

// ========== API Routes ==========

// Stats overview
app.get('/api/stats', async (req, res) => {
  try {
    const total = await pool.query('SELECT COUNT(*) as total FROM notices');
    const byLevel = await pool.query(`
      SELECT level_1, COUNT(*) as count 
      FROM notices GROUP BY level_1 
      ORDER BY CASE level_1 WHEN '中央' THEN 0 WHEN '省级' THEN 1 ELSE 2 END, count DESC
    `);
    const provinces = await pool.query(`
      SELECT DISTINCT unnest(provinces) as province, COUNT(*) as count
      FROM notices WHERE provinces IS NOT NULL AND array_length(provinces,1)>0
      GROUP BY province ORDER BY count DESC
    `);
    const tags = await pool.query(`
      SELECT DISTINCT unnest(tags) as tag, COUNT(*) as count
      FROM notices WHERE tags IS NOT NULL AND array_length(tags,1)>0
      GROUP BY tag ORDER BY count DESC
    `);
    res.json({
      total: parseInt(total.rows[0].total),
      byLevel: byLevel.rows,
      provinces: provinces.rows,
      tags: tags.rows
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// List notices with filters
app.get('/api/notices', async (req, res) => {
  try {
    const { search, level_1, tag, province, page = 1, limit = 20 } = req.query;
    let conditions = [];
    let params = [];
    let idx = 1;

    if (search) {
      conditions.push(`(title ILIKE $${idx} OR content ILIKE $${idx})`);
      params.push(`%${search}%`);
      idx++;
    }
    if (level_1) {
      const levels = level_1.split(',');
      conditions.push(`level_1 = ANY($${idx})`);
      params.push(levels);
      idx++;
    }
    if (tag) {
      const tags = tag.split(',');
      conditions.push(`tags && $${idx}`);
      params.push(tags);
      idx++;
    }
    if (province) {
      const provs = province.split(',');
      conditions.push(`provinces && $${idx}`);
      params.push(provs);
      idx++;
    }

    const where = conditions.length > 0 ? 'WHERE ' + conditions.join(' AND ') : '';
    const offset = (parseInt(page) - 1) * parseInt(limit);

    const countQ = await pool.query(`SELECT COUNT(*) FROM notices ${where}`, params);
    const dataQ = await pool.query(
      `SELECT id, title, source_url, level_1, level_2, publish_date, 
              LEFT(content, 300) as content_preview, summary, tags, provinces, case_count
       FROM notices ${where}
       ORDER BY publish_date DESC NULLS LAST, scraped_at DESC
       LIMIT $${idx} OFFSET $${idx + 1}`,
      [...params, parseInt(limit), offset]
    );

    res.json({
      total: parseInt(countQ.rows[0].count),
      page: parseInt(page),
      limit: parseInt(limit),
      data: dataQ.rows
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Single notice detail
app.get('/api/notices/:id', async (req, res) => {
  try {
    const result = await pool.query('SELECT * FROM notices WHERE id = $1', [req.params.id]);
    if (result.rows.length === 0) return res.status(404).json({ error: 'Not found' });
    res.json(result.rows[0]);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// AI search via Ollama (CA server)
app.post('/api/ai-search', async (req, res) => {
  try {
    const { query } = req.body;
    if (!query) return res.status(400).json({ error: 'query required' });

    // Step 1: Use Ollama to convert natural language to SQL-like conditions
    const ollamaPrompt = `你是一个政府通报数据库查询助手。用户会用自然语言描述需求，你需要将其转换为结构化的搜索条件。

数据库结构:
- notices 表
- 字段: title(标题), content(正文), level_1(一级分类:中央/省级), tags(问题标签数组:层层加码/形式主义/数据造假/官僚主义/脱离实际/考核泛滥/资源浪费/强制摊派), provinces(省份数组), publish_date(发布日期)

用户查询: "${query}"

请返回JSON格式的搜索条件，只包含需要的字段:
{"search_keywords": "搜索关键词", "tags": ["标签1"], "provinces": ["省份"], "level_1": "中央或省级"}

只返回JSON，不要其他内容。`;

    const ollamaResp = await new Promise((resolve, reject) => {
      const postData = JSON.stringify({
        model: 'qwen3.5:9b',
        prompt: ollamaPrompt,
        stream: false,
        options: { temperature: 0 }
      });
      const options = {
        hostname: '192.168.123.33',
        port: 11434,
        path: '/api/generate',
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(postData) },
        timeout: 30000
      };
      const req2 = http.request(options, (resp) => {
        let data = '';
        resp.on('data', chunk => data += chunk);
        resp.on('end', () => {
          try { resolve(JSON.parse(data)); } catch(e) { resolve({response: data}); }
        });
      });
      req2.on('error', reject);
      req2.on('timeout', () => { req2.destroy(); reject(new Error('Ollama timeout')); });
      req2.write(postData);
      req2.end();
    });

    // Parse AI response
    let conditions;
    try {
      const text = ollamaResp.response || '';
      const jsonMatch = text.match(/\{[^}]+\}/);
      conditions = jsonMatch ? JSON.parse(jsonMatch[0]) : { search_keywords: query };
    } catch(e) {
      conditions = { search_keywords: query };
    }

    // Step 2: Build SQL query
    let sqlConditions = [];
    let params = [];
    let idx = 1;

    if (conditions.search_keywords) {
      sqlConditions.push(`(title ILIKE $${idx} OR content ILIKE $${idx} OR summary ILIKE $${idx})`);
      params.push(`%${conditions.search_keywords}%`);
      idx++;
    }
    if (conditions.tags && conditions.tags.length > 0) {
      sqlConditions.push(`tags && $${idx}`);
      params.push(conditions.tags);
      idx++;
    }
    if (conditions.provinces && conditions.provinces.length > 0) {
      sqlConditions.push(`provinces && $${idx}`);
      params.push(conditions.provinces);
      idx++;
    }
    if (conditions.level_1) {
      sqlConditions.push(`level_1 = $${idx}`);
      params.push(conditions.level_1);
      idx++;
    }

    const where = sqlConditions.length > 0 ? 'WHERE ' + sqlConditions.join(' AND ') : '';
    const result = await pool.query(
      `SELECT id, title, level_1, publish_date, tags, provinces, 
              LEFT(content, 300) as content_preview
       FROM notices ${where}
       ORDER BY publish_date DESC LIMIT 20`,
      params
    );

    // Step 3: Generate AI summary of results
    let summary = '';
    if (result.rows.length > 0) {
      const titles = result.rows.map(r => r.title.substring(0, 60)).join('；');
      summaryPrompt = `根据以下政府通报查询结果，用1-2句话概括找到的内容。\n查询: ${query}\n找到 ${result.rows.length} 条结果: ${titles}`;
      
      const sumResp = await new Promise((resolve, reject) => {
        const pd = JSON.stringify({ model: 'qwen3.5:9b', prompt: summaryPrompt, stream: false, options: { temperature: 0.3 } });
        const opt = {
          hostname: '192.168.123.33', port: 11434, path: '/api/generate', method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(pd) },
          timeout: 30000
        };
        const r = http.request(opt, resp => { let d=''; resp.on('data',c=>d+=c); resp.on('end',()=>{try{resolve(JSON.parse(d));}catch(e){resolve({response:d});}}); });
        r.on('error', reject);
        r.on('timeout', () => { r.destroy(); reject(new Error('timeout')); });
        r.write(pd);
        r.end();
      });
      summary = sumResp.response || '';
    }

    res.json({
      query,
      ai_conditions: conditions,
      total: result.rows.length,
      summary: summary.trim(),
      data: result.rows
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ========== 情况反映 API ==========

// 提交反映
app.post('/api/reports', async (req, res) => {
  try {
    const { city, district, unit, content } = req.body;
    if (!city || !district || !unit || !content) {
      return res.status(400).json({ error: '所有字段均为必填' });
    }
    const result = await pool.query(
      `INSERT INTO reports (city, district, unit, content) VALUES ($1, $2, $3, $4) RETURNING id`,
      [city, district, unit, content]
    );
    res.json({ success: true, id: result.rows[0].id });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// 查询反映列表（管理端）
app.get('/api/reports', async (req, res) => {
  try {
    const { status, city, keyword } = req.query;
    let conditions = [];
    let params = [];
    let idx = 1;
    if (status) { conditions.push(`status = $${idx}`); params.push(status); idx++; }
    if (city) { conditions.push(`city = $${idx}`); params.push(city); idx++; }
    if (keyword) { conditions.push(`(unit ILIKE $${idx} OR content ILIKE $${idx} OR city ILIKE $${idx} OR district ILIKE $${idx})`); params.push(`%${keyword}%`); idx++; }
    const where = conditions.length ? 'WHERE ' + conditions.join(' AND ') : '';
    
    const countQ = await pool.query(`SELECT COUNT(*) as total, status FROM reports ${where} GROUP BY status`, params);
    const dataQ = await pool.query(`SELECT * FROM reports ${where} ORDER BY created_at DESC`, params);
    
    const stats = {};
    let total = 0;
    countQ.rows.forEach(r => { stats[r.status] = parseInt(r.total); total += parseInt(r.total); });
    // If no filters, get total from all
    if (!conditions.length) {
      const allQ = await pool.query('SELECT COUNT(*) as total FROM reports');
      total = parseInt(allQ.rows[0].total);
    }
    
    res.json({ total: dataQ.rows.length, stats, data: dataQ.rows });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// 单条反映详情
app.get('/api/reports/:id', async (req, res) => {
  try {
    const result = await pool.query('SELECT * FROM reports WHERE id = $1', [req.params.id]);
    if (result.rows.length === 0) return res.status(404).json({ error: 'Not found' });
    res.json(result.rows[0]);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// 更新反映（管理端）
app.put('/api/reports/:id', async (req, res) => {
  try {
    const { status, city, district, unit, content, admin_note } = req.body;
    await pool.query(
      `UPDATE reports SET status=COALESCE($1,status), city=COALESCE($2,city), district=COALESCE($3,district),
       unit=COALESCE($4,unit), content=COALESCE($5,content), admin_note=$6, updated_at=NOW() WHERE id=$7`,
      [status, city, district, unit, content, admin_note, req.params.id]
    );
    res.json({ success: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// 删除反映（管理端）
app.delete('/api/reports/:id', async (req, res) => {
  try {
    await pool.query('DELETE FROM reports WHERE id = $1', [req.params.id]);
    res.json({ success: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Catch-all: serve index.html
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

const PORT = process.env.PORT || 3008;
app.listen(PORT, '0.0.0.0', () => {
  console.log(`通报数据库服务运行在 http://0.0.0.0:${PORT}`);
});
