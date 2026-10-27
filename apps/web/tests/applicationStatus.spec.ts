import { describe, expect, it } from 'vitest'

import {
  eventLabel,
  formatDate,
  isTerminal,
  nextStatuses,
  statusLabel,
  statusTagType,
  toIsoDate,
} from '@/utils/applicationStatus'

describe('applicationStatus helpers', () => {
  it('状态标签与颜色按漏斗推进', () => {
    expect(statusTagType('offer')).toBe('success')
    expect(statusTagType('rejected')).toBe('danger')
    expect(statusTagType('applied')).toBe('primary')
    expect(statusTagType('written_test')).toBe('warning')
    expect(statusTagType('not_applied')).toBe('info')
    expect(statusLabel('interview_done')).toBe('已面试')
  })

  it('没有「正在面试」状态', () => {
    expect(statusLabel('interviewing')).toBe('interviewing')
    expect(isTerminal('offer')).toBe(true)
    expect(isTerminal('applied')).toBe(false)
  })

  it('合法转换与后端一致', () => {
    expect(nextStatuses('not_applied')).toEqual(['applied'])
    expect(nextStatuses('applied')).toEqual([
      'written_test',
      'interview_done',
      'offer',
      'rejected',
      'withdrawn',
    ])
    expect(nextStatuses('offer')).toEqual(['withdrawn'])
    // 误操作修正：终态可回到「已投递」，后端会记 status_corrected。
    expect(nextStatuses('rejected')).toEqual(['applied'])
    expect(nextStatuses('withdrawn')).toEqual(['applied'])
  })

  it('日期格式化与 ISO 转换', () => {
    expect(formatDate(null)).toBe('—')
    expect(formatDate('2026-03-02T09:00:00+00:00')).toBe('2026-03-02')
    expect(toIsoDate('2026-03-02')).toBe('2026-03-02T00:00:00+00:00')
    expect(toIsoDate('')).toBeNull()
  })

  it('事件类型有中文标签', () => {
    expect(eventLabel('stage_detail_updated')).toBe('更新阶段详情')
    expect(eventLabel('status_corrected')).toBe('修正状态')
    expect(eventLabel('resume_version_locked')).toBe('锁定简历版本')
    expect(eventLabel('unknown_event')).toBe('unknown_event')
  })
})
