import unittest

from mock import Mock

from boto.cloudformation.stack import Stack

from velvet.cloudformation.stack import StackNotReadyException, validate_stack

class TestCloudFormationValidateStack(unittest.TestCase):

	def test_validate_valid(self):

		valid_statuses = [
			# Successful creation of one or more stacks.
			'CREATE_COMPLETE',
			# Successful update of one or more stacks.
			'UPDATE_COMPLETE',
			# Successful return of one or more stacks to a previous working state after a failed stack update.
			'UPDATE_ROLLBACK_COMPLETE',
			# Ongoing removal of old resources for one or more stacks after a successful stack update. For stack updates that require resources to be replaced, AWS CloudFormation creates the new resources first and then deletes the old resources to help reduce any interruptions with your stack. In this state, the stack has been updated and is, usable, but AWS CloudFormation is still deleting the old resources.
			'UPDATE_COMPLETE_CLEANUP_IN_PROGRESS'
		]

		for status in valid_statuses:
			stack = Stack()
			stack.stack_name = 'TestStack-' + status
			stack.stack_status = status

			self.assertEquals(stack.stack_status, status)
			try:
				validate_stack(stack)
			except StackNotReadyException:
				self.fail('validate_stack threw an exception on a valid value ' + status)


	def test_validate_invalid(self):

		valid_statuses = [
			# Ongoing creation of one or more stacks.
			'CREATE_IN_PROGRESS',
			# Unsuccessful creation of one or more stacks. View the stack events to see any associated error messages. Possible reasons for a failed creation include insufficient permissions to work with all resources in the stack, parameter values rejected by an AWS service, or a timeout during resource creation.,
			'CREATE_FAILED'
			# Successful deletion of one or more stacks. Deleted stacks are retained and viewable for 90 days.
			'DELETE_COMPLETE',
			# Unsuccessful deletion of one or more stacks. Because the delete failed, you might have some resources that are still running; however, you cannot work with or update the stack. Delete the stack again or view the stack events to see any associated error messages.,
			'DELETE_FAILED'
			# Ongoing removal of one or more stacks.
			'DELETE_IN_PROGRESS',
			# Successful removal of one or more stacks after a failed stack creation or after an explicitly canceled stack creation. Any resources that were created during the create stack action are deleted.,
			'ROLLBACK_COMPLETE'
			# Unsuccessful removal of one or more stacks after a failed stack creation or after an explicitly canceled stack creation. Delete the stack or view the stack events to see any associated error messages.,
			'ROLLBACK_FAILED'
			# Ongoing removal of one or more stacks after a failed stack creation or after an explicitly cancelled stack creation.
			'ROLLBACK_IN_PROGRESS',
			# Ongoing update of one or more stacks.
			'UPDATE_IN_PROGRESS',
			# Unsuccessful return of one or more stacks to a previous working state after a failed stack update. You can delete the stack or contact customer support to restore the stack to a usable state.
			'UPDATE_ROLLBACK_FAILED',
			# Ongoing return of one or more stacks to the previous working state after failed stack update.
			'UPDATE_ROLLBACK_IN_PROGRESS',
            # Ongoing removal of new resources for one or more stacks after a failed stack update. In this state, the stack has been rolled back to its previous working state and is usable, but AWS CloudFormation is still deleting any new resources it created during the stack update.,
			'UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS',
		]

		for status in valid_statuses:
			stack = Stack()
			stack.stack_name = 'TestStack-' + status
			stack.stack_status = status

			self.assertEquals(stack.stack_status, status)
			self.assertRaises(Exception, validate_stack, stack)		