import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'

import DocumentChunkCard from '@/components/DocumentChunkCard.vue'
import type { DocumentChunk } from '@/types/documents'

const chunk: DocumentChunk = {
  id: 'chunk-1',
  document_id: 'document-1',
  position: 0,
  section_path: ['星河智能 AI 实习', '任职要求'],
  chunk_type: 'requirement',
  content: '熟悉 Python、FastAPI 和 PostgreSQL。',
  contextualized_content: '文档：星河智能 AI 实习\n章节：任职要求\n熟悉 Python。',
  char_count: 31,
  estimated_token_count: 28,
  content_hash: 'abc123',
  parser_version: 'rule-parser-v1',
  index_version: 'title-aware-v1',
  embedding_model: null,
}

describe('DocumentChunkCard', () => {
  it('shows provenance, semantic type and size metadata', () => {
    const wrapper = mount(DocumentChunkCard, {
      props: { chunk },
      global: { plugins: [ElementPlus] },
    })

    expect(wrapper.text()).toContain('星河智能 AI 实习 / 任职要求')
    expect(wrapper.text()).toContain('熟悉 Python、FastAPI 和 PostgreSQL。')
    expect(wrapper.text()).toContain('任职要求')
    expect(wrapper.text()).toContain('约 28 tokens')
    expect(wrapper.text()).toContain('title-aware-v1')
  })
})
