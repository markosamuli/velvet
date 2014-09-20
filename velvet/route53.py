import boto
import velvet.cloudformation as cf
from boto.route53.record import ResourceRecordSets
import logging

def update_elb_dns(stack, elb_attr, hosted_zone_id, dns_name):

    ttl = 60
    elb_dns = cf.get_stack_output_value(stack, elb_attr)
    dns_record_name = dns_name + "."

    conn = boto.connect_route53()

    existing_entries = conn.get_all_rrsets(hosted_zone_id, "CNAME", dns_name)

    changes = ResourceRecordSets(conn, hosted_zone_id)
    for item in existing_entries:
        
        if dns_record_name != item.name:
            logging.info('Nothing to change for %s', dns_name)
            continue

        for record in item.resource_records:
            logging.warning('Deleting CNAME entry {0} -> {1}'.format(dns_name, record))
            change = changes.add_change("DELETE", dns_name, "CNAME", ttl=ttl)
            change.add_value(record)

    logging.warning("Adding CNAME entry %s -> %s", dns_name, elb_dns)
    change = changes.add_change("CREATE", dns_name, "CNAME", ttl=ttl)
    change.add_value(elb_dns)
    
    try:
        changes.commit()
        print '*** DNS record updated'
        print '{0} IN CNAME {1}'.format(dns_name, elb_dns)
    except Exception, e:
        logging.error(e)