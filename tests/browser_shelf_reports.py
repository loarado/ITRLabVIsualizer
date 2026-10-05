import unittest
import browser_features
from playwright.sync_api import expect

class ShelfReports(unittest.TestCase):
    setUp=browser_features.Features.setUp
    tearDown=browser_features.Features.tearDown
    login=browser_features.Features.login

    def test_anonymous_failure_safe_text_duplicate_and_admin_review(self):
        p=self.page;p.locator('[data-id="R01"]').click()
        expect(p.locator('#explorerContent .shelf-report-action')).to_have_count(1)
        p.get_by_role('button',name='Report incorrect information').click()
        p.locator('#report-text').fill('<img src=x onerror=alert(1)> Wrong label')
        p.route('**/api/reports',lambda route:route.fulfill(status=500,content_type='application/json',body='{"error":"Simulated report failure"}'))
        p.locator('#report-submit').click();expect(p.locator('#report-feedback')).to_contain_text('Your text is retained')
        expect(p.locator('#report-text')).to_have_value('<img src=x onerror=alert(1)> Wrong label')
        p.unroute('**/api/reports');self.errors[:]=[e for e in self.errors if 'status of 500' not in e]
        p.evaluate("document.querySelector('#shelfReportForm').requestSubmit();document.querySelector('#shelfReportForm').requestSubmit()")
        expect(p.locator('#report-feedback')).to_contain_text('Report submitted');p.locator('#report-close').click();p.locator('#closeExplorer').click()
        self.login();expect(p.locator('#reportReviewButton')).to_contain_text('1 pending')
        p.locator('#reportReviewButton').click();expect(p.locator('#reportReviewList')).to_contain_text('<img src=x onerror=alert(1)> Wrong label')
        expect(p.locator('#reportReviewList img')).to_have_count(0)
        p.get_by_role('button',name='Resolve',exact=True).click();expect(p.locator('#reportReviewButton')).to_contain_text('0 pending')
        expect(p.locator('#reportReviewList')).to_contain_text('resolved');p.locator('#reportReviewClose').click()
        p.locator('#auth').click();p.wait_for_function('!isAdmin');expect(p.locator('#reportReviewButton')).to_be_hidden()

if __name__=='__main__':unittest.main()
