import React from 'react'
import {Collapse} from 'reactstrap';
import ReactJson from 'react-json-view'
import {
    DataTableRow,
    DataTableCell
} from '@rmwc/data-table';
import '@rmwc/data-table/data-table.css';
import {Icon} from 'rmwc/Icon';
import { LinearProgress } from '@rmwc/linear-progress';
import '@material/linear-progress/dist/mdc.linear-progress.css';


export default class SlaBountyItem extends React.Component {

    constructor(props) {
        super(props);
        this.state = {
            collapse: false,
        };
        //
        this.toggle = this.toggle.bind(this);
    }

    toggle() {
        this.setState({ collapse: !this.state.collapse });
    }


    /////////////////////////////

    render() {

        return (
            <DataTableRow>
                <DataTableCell>{this.props.v['tx_dt']}</DataTableCell>
                    <DataTableCell>{this.props.v['bounty']}</DataTableCell>
                    <DataTableCell>{this.props.v['latency']}</DataTableCell>
                    <DataTableCell>{this.props.v['downtime']}</DataTableCell>
                    <DataTableCell>{this.props.v['bounty_receipt']['gas_used']}</DataTableCell>
                    <DataTableCell>
                        <div onClick={this.toggle} className='hand-cursor md-icon'>
                            <Icon icon="arrow_drop_down" iconOptions={{strategy: 'ligature'}}
                                  className={"md-icon " + (this.state.collapse ? 'icon-active' : 'accent-icon')}
                            />
                        </div>
                        <Collapse isOpen={this.state.collapse}>
                            <div style={{padding: '10px'}}>
                                {this.state.collapse ?
                                    <ReactJson src={this.props.v['bounty_receipt']}
                                                                  theme={this.props.darkMode ? 'hopscotch' : 'rjv-default'}
                                                                  style={{backgroundColor: 'transparent'}}
                                    />
                                    :
                                    <LinearProgress determinate={false}/>}
                            </div>
                        </Collapse>
                    </DataTableCell>
            </DataTableRow>
        )
    }

}
